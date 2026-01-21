"""Chain configurations for multi-chain balance checking."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EVMChain:
    """Configuration for an EVM-compatible chain."""
    name: str
    chain_id: int
    rpc_url: str
    symbol: str
    explorer: str
    decimals: int = 18


@dataclass
class SolanaCluster:
    """Configuration for Solana cluster."""
    name: str
    rpc_url: str
    symbol: str = "SOL"
    explorer: str = "https://solscan.io"
    decimals: int = 9


# Popular EVM chains with free public RPCs
EVM_CHAINS = {
    "ethereum": EVMChain(
        name="Ethereum",
        chain_id=1,
        rpc_url="https://eth.llamarpc.com",
        symbol="ETH",
        explorer="https://etherscan.io"
    ),
    "base": EVMChain(
        name="Base",
        chain_id=8453,
        rpc_url="https://mainnet.base.org",
        symbol="ETH",
        explorer="https://basescan.org"
    ),
    "arbitrum": EVMChain(
        name="Arbitrum One",
        chain_id=42161,
        rpc_url="https://arb1.arbitrum.io/rpc",
        symbol="ETH",
        explorer="https://arbiscan.io"
    ),
    "optimism": EVMChain(
        name="Optimism",
        chain_id=10,
        rpc_url="https://mainnet.optimism.io",
        symbol="ETH",
        explorer="https://optimistic.etherscan.io"
    ),
    "polygon": EVMChain(
        name="Polygon",
        chain_id=137,
        rpc_url="https://polygon-rpc.com",
        symbol="MATIC",
        explorer="https://polygonscan.com"
    ),
    "bsc": EVMChain(
        name="BNB Smart Chain",
        chain_id=56,
        rpc_url="https://bsc-dataseed.binance.org",
        symbol="BNB",
        explorer="https://bscscan.com"
    ),
    "avalanche": EVMChain(
        name="Avalanche C-Chain",
        chain_id=43114,
        rpc_url="https://api.avax.network/ext/bc/C/rpc",
        symbol="AVAX",
        explorer="https://snowtrace.io"
    ),
    "fantom": EVMChain(
        name="Fantom",
        chain_id=250,
        rpc_url="https://rpc.ftm.tools",
        symbol="FTM",
        explorer="https://ftmscan.com"
    ),
    "zksync": EVMChain(
        name="zkSync Era",
        chain_id=324,
        rpc_url="https://mainnet.era.zksync.io",
        symbol="ETH",
        explorer="https://explorer.zksync.io"
    ),
    "linea": EVMChain(
        name="Linea",
        chain_id=59144,
        rpc_url="https://rpc.linea.build",
        symbol="ETH",
        explorer="https://lineascan.build"
    ),
    "scroll": EVMChain(
        name="Scroll",
        chain_id=534352,
        rpc_url="https://rpc.scroll.io",
        symbol="ETH",
        explorer="https://scrollscan.com"
    ),
    "mantle": EVMChain(
        name="Mantle",
        chain_id=5000,
        rpc_url="https://rpc.mantle.xyz",
        symbol="MNT",
        explorer="https://explorer.mantle.xyz"
    ),
    "blast": EVMChain(
        name="Blast",
        chain_id=81457,
        rpc_url="https://rpc.blast.io",
        symbol="ETH",
        explorer="https://blastscan.io"
    ),
}

# Solana clusters
SOLANA_CLUSTERS = {
    "mainnet": SolanaCluster(
        name="Solana Mainnet",
        rpc_url="https://api.mainnet-beta.solana.com",
        explorer="https://solscan.io"
    ),
}

# Default chains to check
DEFAULT_EVM_CHAINS = ["ethereum", "base", "arbitrum", "optimism", "polygon", "bsc"]
DEFAULT_SOLANA_CLUSTERS = ["mainnet"]
