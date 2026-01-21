#!/usr/bin/env python3
"""
Multi-Chain Balance Checker

Check balances across multiple blockchain networks for various key types:
- Ethereum private keys (64 hex chars, with or without 0x prefix)
- Solana private keys (base58 or JSON array format)
- BIP-39 seed phrases (12-24 words)

Usage:
    python check_balances.py keys.txt
    python check_balances.py keys.txt --chains ethereum,base,arbitrum
    python check_balances.py keys.txt --all-chains
    python check_balances.py keys.txt --only-with-balance
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.balance_checker import KeyDetector, KeyType, BalanceChecker
from src.balance_checker.chains import EVM_CHAINS, SOLANA_CLUSTERS


def print_header():
    """Print the tool header."""
    print("=" * 70)
    print("  Multi-Chain Balance Checker")
    print("  Supports: ETH keys, SOL keys, Seed phrases")
    print("  Checks: Native balances + ERC-20/SPL tokens")
    print("=" * 70)
    print()


def print_key_info(key):
    """Print information about a detected key."""
    key_type_display = {
        KeyType.ETH_PRIVATE_KEY: "Ethereum Private Key",
        KeyType.SOLANA_PRIVATE_KEY: "Solana Private Key",
        KeyType.SEED_PHRASE: "Seed Phrase (Mnemonic)",
    }
    print(f"  Type: {key_type_display.get(key.key_type, 'Unknown')}")
    print(f"  Line: {key.line_number}")

    # Show truncated key for identification
    if key.key_type == KeyType.SEED_PHRASE:
        words = key.raw_value.split()
        preview = f"{words[0]} {words[1]} ... {words[-2]} {words[-1]} ({len(words)} words)"
    else:
        preview = f"{key.raw_value[:8]}...{key.raw_value[-8:]}"
    print(f"  Key: {preview}")


def print_result(result, only_with_balance: bool = False):
    """Print the result for a single wallet."""
    print("-" * 70)
    print_key_info(result.key_info)

    if result.address_evm:
        print(f"  EVM Address: {result.address_evm}")
    if result.address_solana:
        print(f"  SOL Address: {result.address_solana}")

    if result.error:
        print(f"  Error: {result.error}")

    if not result.balances:
        print("  No balances checked")
        return

    print()

    # Group balances
    balances_with_funds = [b for b in result.balances if b.has_balance]
    balances_with_tokens = [b for b in result.balances if b.tokens]
    balances_empty = [b for b in result.balances if not b.has_balance and not b.tokens and "Error" not in b.balance_formatted]
    balances_error = [b for b in result.balances if "Error" in b.balance_formatted]

    if balances_with_funds:
        print("  NATIVE BALANCE:")
        for bal in balances_with_funds:
            print(f"     {bal.chain_name}: {bal.balance_formatted} {bal.symbol}")
            print(f"       -> {bal.explorer_url}")

    if balances_with_tokens:
        print("  TOKENS:")
        for bal in balances_with_tokens:
            for token in bal.tokens:
                usd_str = f" (${token.usd_value:.2f})" if token.usd_value else ""
                print(f"     {bal.chain_name} | {token.token_symbol}: {token.balance_formatted}{usd_str}")
                print(f"       Token: {token.token_name}")
                if token.token_address:
                    print(f"       Contract: {token.token_address[:20]}...")

    if not only_with_balance:
        if balances_empty:
            print(f"  Empty ({len(balances_empty)}): ", end="")
            chains = [b.chain_name for b in balances_empty]
            print(", ".join(chains))

        if balances_error:
            print(f"  Errors ({len(balances_error)}):")
            for bal in balances_error:
                print(f"     {bal.chain_name}: {bal.balance_formatted}")


def main():
    parser = argparse.ArgumentParser(
        description="Check balances across multiple blockchains for various key types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_balances.py my_keys.txt
  python check_balances.py keys.txt --chains ethereum,base,polygon
  python check_balances.py keys.txt --all-chains
  python check_balances.py keys.txt --only-with-balance

Key file format (one key per line):
  # Comment lines start with #
  0xabc123...def456  (Ethereum private key with 0x)
  abc123...def456    (Ethereum private key without 0x)
  5abc...xyz         (Solana base58 private key)
  [1,2,3,...,64]     (Solana JSON array private key)
  word1 word2 ... word12  (12-word seed phrase)
  word1 word2 ... word24  (24-word seed phrase)
        """
    )

    parser.add_argument(
        "keyfile",
        help="Path to file containing keys (one per line)"
    )

    parser.add_argument(
        "--chains",
        type=str,
        default=None,
        help=f"Comma-separated list of EVM chains to check. Available: {', '.join(EVM_CHAINS.keys())}"
    )

    parser.add_argument(
        "--all-chains",
        action="store_true",
        help="Check all supported chains (slower but comprehensive)"
    )

    parser.add_argument(
        "--only-with-balance",
        action="store_true",
        help="Only show wallets that have balance"
    )

    parser.add_argument(
        "--no-solana",
        action="store_true",
        help="Skip Solana balance checks"
    )

    parser.add_argument(
        "--no-tokens",
        action="store_true",
        help="Skip ERC-20 and SPL token balance checks (faster, native only)"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="RPC request timeout in seconds (default: 10)"
    )

    parser.add_argument(
        "--list-chains",
        action="store_true",
        help="List all supported chains and exit"
    )

    args = parser.parse_args()

    # Handle --list-chains
    if args.list_chains:
        print("Supported EVM chains:")
        for key, chain in EVM_CHAINS.items():
            print(f"  {key:12} - {chain.name} ({chain.symbol})")
        print("\nSupported Solana clusters:")
        for key, cluster in SOLANA_CLUSTERS.items():
            print(f"  {key:12} - {cluster.name}")
        return 0

    # Check if file exists
    keyfile = Path(args.keyfile)
    if not keyfile.exists():
        print(f"Error: File not found: {keyfile}")
        return 1

    print_header()

    # Parse keys first
    print(f"Reading keys from: {keyfile}")
    keys = KeyDetector.parse_keys_from_file(str(keyfile))

    if not keys:
        print("No valid keys found in file!")
        print("\nSupported formats:")
        print("  - Ethereum private key (64 hex chars, with or without 0x)")
        print("  - Solana private key (base58 or JSON array)")
        print("  - Seed phrase (12, 15, 18, 21, or 24 words)")
        return 1

    # Count key types
    eth_keys = sum(1 for k in keys if k.key_type == KeyType.ETH_PRIVATE_KEY)
    sol_keys = sum(1 for k in keys if k.key_type == KeyType.SOLANA_PRIVATE_KEY)
    seed_phrases = sum(1 for k in keys if k.key_type == KeyType.SEED_PHRASE)

    print(f"\nFound {len(keys)} valid keys:")
    if eth_keys:
        print(f"  - {eth_keys} Ethereum private key(s)")
    if sol_keys:
        print(f"  - {sol_keys} Solana private key(s)")
    if seed_phrases:
        print(f"  - {seed_phrases} seed phrase(s)")

    # Determine chains to check
    if args.all_chains:
        evm_chains = list(EVM_CHAINS.keys())
    elif args.chains:
        evm_chains = [c.strip() for c in args.chains.split(",")]
        # Validate chains
        invalid = [c for c in evm_chains if c not in EVM_CHAINS]
        if invalid:
            print(f"Warning: Unknown chains ignored: {', '.join(invalid)}")
            evm_chains = [c for c in evm_chains if c in EVM_CHAINS]
    else:
        evm_chains = None  # Use default

    solana_clusters = None if args.no_solana else ["mainnet"]

    # Initialize checker
    checker = BalanceChecker(
        evm_chains=evm_chains,
        solana_clusters=solana_clusters,
        timeout=args.timeout,
        check_tokens=not args.no_tokens
    )

    chains_info = evm_chains or checker.evm_chains
    print(f"\nChecking balances on {len(chains_info)} EVM chain(s): {', '.join(chains_info)}")
    if solana_clusters:
        print(f"Checking Solana: {', '.join(solana_clusters)}")
    if not args.no_tokens:
        print("Token checking: ENABLED (ERC-20 + SPL tokens)")
    else:
        print("Token checking: DISABLED (native only)")
    print("\nThis may take a moment...")
    print()

    # Check balances
    try:
        results = checker.check_file(str(keyfile))
    except Exception as e:
        print(f"Error checking balances: {e}")
        return 1

    # Print results
    wallets_with_balance = []
    total_chains_with_balance = 0
    total_tokens = 0

    for result in results:
        if args.only_with_balance and not result.has_any_balance:
            continue
        print_result(result, args.only_with_balance)
        if result.has_any_balance:
            wallets_with_balance.append(result)
            total_chains_with_balance += result.total_chains_with_balance
            total_tokens += result.total_tokens

    # Summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Total keys checked: {len(keys)}")
    print(f"  Wallets with balance: {len(wallets_with_balance)}")
    print(f"  Total chain balances found: {total_chains_with_balance}")
    if total_tokens > 0:
        print(f"  Total tokens found: {total_tokens}")

    if wallets_with_balance:
        print("\n  Wallets with funds:")
        for result in wallets_with_balance:
            addr = result.address_evm or result.address_solana
            for bal in result.balances:
                if bal.has_balance:
                    print(f"    - {bal.chain_name}: {bal.balance_formatted} {bal.symbol}")
                    print(f"      {bal.explorer_url}")
                for token in bal.tokens:
                    usd_str = f" (${token.usd_value:.2f})" if token.usd_value else ""
                    print(f"    - {bal.chain_name} | {token.token_symbol}: {token.balance_formatted}{usd_str}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
