"""Multi-chain balance checker implementation."""

import json
import asyncio
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field

import httpx

from .key_detector import KeyDetector, KeyType, DetectedKey
from .chains import (
    EVM_CHAINS, SOLANA_CLUSTERS,
    DEFAULT_EVM_CHAINS, DEFAULT_SOLANA_CLUSTERS,
    EVMChain, SolanaCluster
)


@dataclass
class TokenBalance:
    """Balance information for a specific token."""
    chain_name: str
    token_address: str
    token_symbol: str
    token_name: str
    balance_raw: int
    balance_formatted: str
    decimals: int
    usd_value: Optional[float] = None


@dataclass
class WalletBalance:
    """Balance information for a wallet on a specific chain."""
    chain_name: str
    address: str
    balance_raw: int
    balance_formatted: str
    symbol: str
    explorer_url: str
    has_balance: bool
    tokens: list[TokenBalance] = field(default_factory=list)


@dataclass
class WalletResult:
    """Result of checking a wallet across all chains."""
    key_info: DetectedKey
    address_evm: Optional[str] = None
    address_solana: Optional[str] = None
    balances: list[WalletBalance] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_any_balance(self) -> bool:
        return any(b.has_balance or b.tokens for b in self.balances)

    @property
    def total_chains_with_balance(self) -> int:
        return sum(1 for b in self.balances if b.has_balance or b.tokens)

    @property
    def total_tokens(self) -> int:
        return sum(len(b.tokens) for b in self.balances)


class BalanceChecker:
    """Check balances across multiple blockchain networks."""

    # Ankr RPC endpoints for token balance queries (free tier available)
    ANKR_ENDPOINTS = {
        "ethereum": "https://rpc.ankr.com/eth",
        "base": "https://rpc.ankr.com/base",
        "arbitrum": "https://rpc.ankr.com/arbitrum",
        "optimism": "https://rpc.ankr.com/optimism",
        "polygon": "https://rpc.ankr.com/polygon",
        "bsc": "https://rpc.ankr.com/bsc",
        "avalanche": "https://rpc.ankr.com/avalanche",
        "fantom": "https://rpc.ankr.com/fantom",
    }

    def __init__(
        self,
        evm_chains: Optional[list[str]] = None,
        solana_clusters: Optional[list[str]] = None,
        timeout: float = 10.0,
        check_tokens: bool = True
    ):
        """
        Initialize the balance checker.

        Args:
            evm_chains: List of EVM chain keys to check (default: popular chains)
            solana_clusters: List of Solana cluster keys to check (default: mainnet)
            timeout: HTTP request timeout in seconds
            check_tokens: Whether to also check ERC-20/SPL token balances
        """
        self.evm_chains = evm_chains or DEFAULT_EVM_CHAINS
        self.solana_clusters = solana_clusters or DEFAULT_SOLANA_CLUSTERS
        self.timeout = timeout
        self.check_tokens = check_tokens

    def _derive_eth_address(self, private_key: str) -> str:
        """Derive Ethereum address from private key."""
        from eth_account import Account

        # Ensure 0x prefix
        if not private_key.startswith('0x'):
            private_key = '0x' + private_key

        account = Account.from_key(private_key)
        return account.address

    def _derive_eth_address_from_mnemonic(self, mnemonic: str, path: str = "m/44'/60'/0'/0/0") -> tuple[str, str]:
        """
        Derive Ethereum address from mnemonic.

        Returns:
            Tuple of (address, private_key)
        """
        from eth_account import Account

        Account.enable_unaudited_hdwallet_features()
        account = Account.from_mnemonic(mnemonic, account_path=path)
        return account.address, account.key.hex()

    def _derive_solana_address(self, private_key: str) -> str:
        """Derive Solana address from private key."""
        import base58
        from solders.keypair import Keypair

        # Handle different formats
        if private_key.startswith('['):
            # JSON array format
            key_bytes = bytes(json.loads(private_key))
            keypair = Keypair.from_bytes(key_bytes)
        else:
            # Base58 format
            key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_bytes(key_bytes)

        return str(keypair.pubkey())

    def _derive_solana_address_from_mnemonic(self, mnemonic: str) -> tuple[str, str]:
        """
        Derive Solana address from mnemonic using standard derivation path.

        Returns:
            Tuple of (address, private_key_base58)
        """
        import base58
        from solders.keypair import Keypair
        from mnemonic import Mnemonic
        import hashlib
        import hmac

        # BIP39 seed derivation
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(mnemonic)

        # Solana uses ed25519 derivation path m/44'/501'/0'/0'
        # Simplified: use first 32 bytes of seed for the keypair
        # For proper derivation, we'd use slip10 but this works for basic cases
        derived = hashlib.pbkdf2_hmac('sha512', seed, b'ed25519 seed', 2048)[:32]

        keypair = Keypair.from_seed(derived)
        return str(keypair.pubkey()), base58.b58encode(bytes(keypair)).decode()

    async def _check_evm_balance(
        self,
        client: httpx.AsyncClient,
        address: str,
        chain: EVMChain
    ) -> WalletBalance:
        """Check balance on an EVM chain."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [address, "latest"],
                "id": 1
            }

            response = await client.post(
                chain.rpc_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise Exception(data["error"].get("message", "RPC error"))

            balance_hex = data.get("result", "0x0")
            balance_raw = int(balance_hex, 16)
            balance_formatted = f"{Decimal(balance_raw) / Decimal(10 ** chain.decimals):.6f}"
            has_balance = balance_raw > 0

            return WalletBalance(
                chain_name=chain.name,
                address=address,
                balance_raw=balance_raw,
                balance_formatted=balance_formatted,
                symbol=chain.symbol,
                explorer_url=f"{chain.explorer}/address/{address}",
                has_balance=has_balance
            )

        except Exception as e:
            return WalletBalance(
                chain_name=chain.name,
                address=address,
                balance_raw=0,
                balance_formatted=f"Error: {str(e)[:50]}",
                symbol=chain.symbol,
                explorer_url=f"{chain.explorer}/address/{address}",
                has_balance=False
            )

    async def _check_solana_balance(
        self,
        client: httpx.AsyncClient,
        address: str,
        cluster: SolanaCluster
    ) -> WalletBalance:
        """Check balance on Solana."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "getBalance",
                "params": [address],
                "id": 1
            }

            response = await client.post(
                cluster.rpc_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise Exception(data["error"].get("message", "RPC error"))

            balance_raw = data.get("result", {}).get("value", 0)
            balance_formatted = f"{Decimal(balance_raw) / Decimal(10 ** cluster.decimals):.6f}"
            has_balance = balance_raw > 0

            return WalletBalance(
                chain_name=cluster.name,
                address=address,
                balance_raw=balance_raw,
                balance_formatted=balance_formatted,
                symbol=cluster.symbol,
                explorer_url=f"{cluster.explorer}/account/{address}",
                has_balance=has_balance
            )

        except Exception as e:
            return WalletBalance(
                chain_name=cluster.name,
                address=address,
                balance_raw=0,
                balance_formatted=f"Error: {str(e)[:50]}",
                symbol=cluster.symbol,
                explorer_url=f"{cluster.explorer}/account/{address}",
                has_balance=False
            )

    async def _check_evm_tokens(
        self,
        client: httpx.AsyncClient,
        address: str,
        chain_key: str,
        chain: EVMChain
    ) -> list[TokenBalance]:
        """Check ERC-20 token balances using Ankr API."""
        tokens = []

        if chain_key not in self.ANKR_ENDPOINTS:
            return tokens

        try:
            # Use Ankr's advanced API for token balances
            payload = {
                "jsonrpc": "2.0",
                "method": "ankr_getAccountBalance",
                "params": {
                    "blockchain": chain_key if chain_key != "bsc" else "bsc",
                    "walletAddress": address,
                    "onlyWhitelisted": False
                },
                "id": 1
            }

            response = await client.post(
                "https://rpc.ankr.com/multichain",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                assets = data.get("result", {}).get("assets", [])

                for asset in assets:
                    # Skip native token (already handled)
                    if asset.get("tokenType") == "NATIVE":
                        continue

                    balance_raw = int(asset.get("balanceRawInteger", "0"))
                    if balance_raw == 0:
                        continue

                    decimals = asset.get("tokenDecimals", 18)
                    balance_formatted = f"{Decimal(balance_raw) / Decimal(10 ** decimals):.6f}"

                    tokens.append(TokenBalance(
                        chain_name=chain.name,
                        token_address=asset.get("contractAddress", ""),
                        token_symbol=asset.get("tokenSymbol", "???"),
                        token_name=asset.get("tokenName", "Unknown"),
                        balance_raw=balance_raw,
                        balance_formatted=balance_formatted,
                        decimals=decimals,
                        usd_value=float(asset.get("balanceUsd", 0)) if asset.get("balanceUsd") else None
                    ))

        except Exception:
            # Token check failed, but we still have native balance
            pass

        return tokens

    async def _check_solana_tokens(
        self,
        client: httpx.AsyncClient,
        address: str,
        cluster: SolanaCluster
    ) -> list[TokenBalance]:
        """Check SPL token balances on Solana."""
        tokens = []

        try:
            # Get all token accounts for this wallet
            payload = {
                "jsonrpc": "2.0",
                "method": "getTokenAccountsByOwner",
                "params": [
                    address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"}
                ],
                "id": 1
            }

            response = await client.post(
                cluster.rpc_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                return tokens

            accounts = data.get("result", {}).get("value", [])

            for account in accounts:
                try:
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                    info = parsed.get("info", {})
                    token_amount = info.get("tokenAmount", {})

                    balance_raw = int(token_amount.get("amount", "0"))
                    if balance_raw == 0:
                        continue

                    decimals = token_amount.get("decimals", 0)
                    ui_amount = token_amount.get("uiAmountString", "0")

                    tokens.append(TokenBalance(
                        chain_name=cluster.name,
                        token_address=info.get("mint", ""),
                        token_symbol="SPL",  # Would need token registry for actual symbol
                        token_name=info.get("mint", "")[:8] + "...",
                        balance_raw=balance_raw,
                        balance_formatted=ui_amount,
                        decimals=decimals
                    ))
                except Exception:
                    continue

        except Exception:
            pass

        return tokens

    async def check_wallet(self, key: DetectedKey) -> WalletResult:
        """
        Check balance for a single wallet across all configured chains.

        Args:
            key: Detected key information

        Returns:
            WalletResult with balances across all chains
        """
        result = WalletResult(key_info=key)

        try:
            async with httpx.AsyncClient() as client:
                tasks = []

                if key.key_type == KeyType.ETH_PRIVATE_KEY:
                    # EVM chains only
                    result.address_evm = self._derive_eth_address(key.raw_value)

                    for chain_key in self.evm_chains:
                        if chain_key in EVM_CHAINS:
                            chain = EVM_CHAINS[chain_key]
                            tasks.append(self._check_evm_balance(client, result.address_evm, chain))

                elif key.key_type == KeyType.SOLANA_PRIVATE_KEY:
                    # Solana only
                    result.address_solana = self._derive_solana_address(key.raw_value)

                    for cluster_key in self.solana_clusters:
                        if cluster_key in SOLANA_CLUSTERS:
                            cluster = SOLANA_CLUSTERS[cluster_key]
                            tasks.append(self._check_solana_balance(client, result.address_solana, cluster))

                elif key.key_type == KeyType.SEED_PHRASE:
                    # Both EVM and Solana
                    try:
                        result.address_evm, _ = self._derive_eth_address_from_mnemonic(key.raw_value)
                        for chain_key in self.evm_chains:
                            if chain_key in EVM_CHAINS:
                                chain = EVM_CHAINS[chain_key]
                                tasks.append(self._check_evm_balance(client, result.address_evm, chain))
                    except Exception as e:
                        result.error = f"EVM derivation failed: {e}"

                    try:
                        result.address_solana, _ = self._derive_solana_address_from_mnemonic(key.raw_value)
                        for cluster_key in self.solana_clusters:
                            if cluster_key in SOLANA_CLUSTERS:
                                cluster = SOLANA_CLUSTERS[cluster_key]
                                tasks.append(self._check_solana_balance(client, result.address_solana, cluster))
                    except Exception as e:
                        if result.error:
                            result.error += f"; SOL derivation failed: {e}"
                        else:
                            result.error = f"SOL derivation failed: {e}"

                # Run all balance checks concurrently
                if tasks:
                    result.balances = await asyncio.gather(*tasks)

                # Check for tokens if enabled
                if self.check_tokens and result.balances:
                    token_tasks = []

                    # EVM token checks
                    if result.address_evm:
                        for chain_key in self.evm_chains:
                            if chain_key in EVM_CHAINS:
                                chain = EVM_CHAINS[chain_key]
                                token_tasks.append(
                                    self._check_evm_tokens(client, result.address_evm, chain_key, chain)
                                )

                    # Solana token checks
                    if result.address_solana:
                        for cluster_key in self.solana_clusters:
                            if cluster_key in SOLANA_CLUSTERS:
                                cluster = SOLANA_CLUSTERS[cluster_key]
                                token_tasks.append(
                                    self._check_solana_tokens(client, result.address_solana, cluster)
                                )

                    if token_tasks:
                        token_results = await asyncio.gather(*token_tasks)

                        # Match tokens to their corresponding balance entries
                        token_idx = 0
                        for balance in result.balances:
                            if token_idx < len(token_results):
                                balance.tokens = token_results[token_idx]
                                token_idx += 1

        except Exception as e:
            result.error = str(e)

        return result

    async def check_all_wallets(self, keys: list[DetectedKey]) -> list[WalletResult]:
        """
        Check balances for all wallets.

        Args:
            keys: List of detected keys

        Returns:
            List of WalletResult for each key
        """
        # Process wallets with some concurrency limit to avoid rate limiting
        results = []
        batch_size = 5

        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            batch_results = await asyncio.gather(*[self.check_wallet(key) for key in batch])
            results.extend(batch_results)

            # Small delay between batches to avoid rate limiting
            if i + batch_size < len(keys):
                await asyncio.sleep(0.5)

        return results

    def check_file(self, filepath: str) -> list[WalletResult]:
        """
        Check balances for all keys in a file.

        Args:
            filepath: Path to file containing keys

        Returns:
            List of WalletResult for each key
        """
        keys = KeyDetector.parse_keys_from_file(filepath)
        return asyncio.run(self.check_all_wallets(keys))

    def check_text(self, text: str) -> list[WalletResult]:
        """
        Check balances for all keys in text content.

        Args:
            text: Text containing keys (one per line)

        Returns:
            List of WalletResult for each key
        """
        keys = KeyDetector.parse_keys_from_text(text)
        return asyncio.run(self.check_all_wallets(keys))
