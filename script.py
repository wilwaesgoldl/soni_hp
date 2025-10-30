import os
import time
import logging
import json
from typing import Dict, Any, List, Optional, Set

import requests
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import BlockNotFound
from web3.types import LogReceipt
from dotenv import load_dotenv

# --- Configuration Loading ---
# In a real-world application, use environment variables for sensitive data.
load_dotenv()

# --- Configuration ---
# This configuration block simulates what would typically be loaded from a config file or environment variables.
# Replace with your actual RPC endpoints (e.g., from Infura, Alchemy).
SOURCE_CHAIN_RPC = os.getenv('SOURCE_CHAIN_RPC', 'https://rpc.sepolia.org')
DESTINATION_CHAIN_RPC = os.getenv('DESTINATION_CHAIN_RPC', 'https://rpc.goerli.mudit.blog/')

# Address of the bridge contract on the source chain.
# This is a placeholder address.
SOURCE_BRIDGE_CONTRACT_ADDRESS = '0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'

# A simplified ABI for the event we are listening for.
# In a real scenario, you would have the full contract ABI.
SOURCE_BRIDGE_CONTRACT_ABI = json.loads('''
[
    {
        "anonymous": false,
        "inputs": [
            {
                "indexed": true,
                "internalType": "address",
                "name": "sender",
                "type": "address"
            },
            {
                "indexed": true,
                "internalType": "address",
                "name": "recipient",
                "type": "address"
            },
            {
                "indexed": true,
                "internalType": "address",
                "name": "token",
                "type": "address"
            },
            {
                "indexed": false,
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            },
            {
                "indexed": false,
                "internalType": "uint256",
                "name": "destinationChainId",
                "type": "uint256"
            },
            {
                "indexed": false,
                "internalType": "uint256",
                "name": "nonce",
                "type": "uint256"
            }
        ],
        "name": "TokensLocked",
        "type": "event"
    }
]
''')

# Number of block confirmations to wait for to mitigate risks from chain re-organizations.
BLOCK_CONFIRMATIONS = 12

# Polling interval in seconds.
POLL_INTERVAL_SECONDS = 10

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Custom Exceptions for Clarity ---
class RPCConnectionError(Exception):
    """Custom exception for errors related to RPC node connection."""
    pass

class EventProcessingError(Exception):
    """Custom exception for errors during the processing of an event."""
    pass

class InvalidEventError(ValueError):
    """Custom exception for events that are malformed or fail validation."""
    pass

# --- Core Components ---

class StateManager:
    """Manages the state of processed events to prevent duplicates.

    In a production system, this would be backed by a persistent database (e.g., Redis, PostgreSQL)
    to ensure state is not lost on restart. For this simulation, we use an in-memory set.
    """
    def __init__(self) -> None:
        self._processed_tx_hashes: Set[str] = set()
        logging.info("StateManager initialized (in-memory).")

    def is_processed(self, tx_hash: str) -> bool:
        """Checks if a transaction hash has already been processed."""
        return tx_hash in self._processed_tx_hashes

    def mark_as_processed(self, tx_hash: str) -> None:
        """Marks a transaction hash as processed."""
        self._processed_tx_hashes.add(tx_hash)
        logging.debug(f"Marked transaction {tx_hash} as processed.")


class BlockchainConnector:
    """Handles all direct interactions with a blockchain via Web3.py."""
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.web3: Optional[Web3] = None
        self.connect()

    def connect(self) -> None:
        """Establishes connection to the blockchain RPC node."""
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not self.web3.is_connected():
                raise RPCConnectionError(f"Failed to connect to RPC endpoint: {self.rpc_url}")
            logging.info(f"Successfully connected to RPC endpoint: {self.rpc_url}")
        except Exception as e:
            raise RPCConnectionError(f"Error connecting to {self.rpc_url}: {e}")

    def get_latest_block_number(self) -> int:
        """Fetches the most recent block number from the connected node."""
        if not self.web3:
            raise RPCConnectionError("Web3 instance not initialized.")
        return self.web3.eth.block_number

    def get_contract(self, address: str, abi: List[Dict[str, Any]]) -> Contract:
        """Creates a Web3.py contract instance."""
        if not self.web3:
            raise RPCConnectionError("Web3 instance not initialized.")
        checksum_address = self.web3.to_checksum_address(address)
        return self.web3.eth.contract(address=checksum_address, abi=abi)

    def get_events(self, contract: Contract, event_name: str, from_block: int, to_block: int) -> List[LogReceipt]:
        """Fetches event logs for a given contract and block range."""
        if not self.web3:
            raise RPCConnectionError("Web3 instance not initialized.")
        try:
            event_filter = contract.events[event_name].create_filter(
                fromBlock=from_block,
                toBlock=to_block
            )
            return event_filter.get_all_entries()
        except BlockNotFound:
            logging.warning(f"Block range not found ({from_block}-{to_block}). This can happen during a re-org. Skipping.")
            return []
        except Exception as e:
            logging.error(f"Failed to get events from block {from_block} to {to_block}: {e}")
            return []

class EventProcessor:
    """Parses, validates, and enriches raw event data.

    This component simulates off-chain logic that might be required before
    acting on a bridge event, such as fetching token prices or validating
    data against an external API.
    """
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        # API for fetching additional data (e.g., token prices)
        self.coingecko_api = 'https://api.coingecko.com/api/v3/simple/price'
        logging.info("EventProcessor initialized.")

    def _get_token_price_usd(self, token_address: str) -> Optional[float]:
        """Simulates fetching token price from an external API like CoinGecko."""
        # This is a mock. A real implementation would map address to coingecko id.
        # For this example, we'll pretend all tokens are 'ethereum'.
        params = {'ids': 'ethereum', 'vs_currencies': 'usd'}
        try:
            response = requests.get(self.coingecko_api, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get('ethereum', {}).get('usd')
        except requests.exceptions.RequestException as e:
            logging.warning(f"Could not fetch token price for {token_address}: {e}")
            return None

    def process_event(self, event: LogReceipt) -> Optional[Dict[str, Any]]:
        """Processes a single raw event log.

        Returns:
            A dictionary with structured event data if processing is successful,
            otherwise None.
        """
        try:
            tx_hash = event['transactionHash'].hex()
            log_index = event['logIndex']

            # 1. Replay Protection: Check if this event has already been processed.
            if self.state_manager.is_processed(f"{tx_hash}-{log_index}"):
                logging.debug(f"Skipping already processed event: tx={tx_hash}, log_index={log_index}")
                return None

            # 2. Parse Event Data
            args = event['args']
            processed_data = {
                'tx_hash': tx_hash,
                'log_index': log_index,
                'block_number': event['blockNumber'],
                'sender': args.get('sender'),
                'recipient': args.get('recipient'),
                'token_address': args.get('token'),
                'amount': args.get('amount'),
                'destination_chain_id': args.get('destinationChainId'),
                'nonce': args.get('nonce')
            }

            # 3. Validate Event Data
            if not all(processed_data.values()):
                raise InvalidEventError(f"Event has missing arguments: {processed_data}")

            # 4. Enrich Data (Example: fetch token price)
            price_usd = self._get_token_price_usd(processed_data['token_address'])
            if price_usd:
                processed_data['amount_usd_estimate'] = (processed_data['amount'] / 10**18) * price_usd

            logging.info(f"Successfully processed event from tx {tx_hash[:10]}... nonce {processed_data['nonce']}")
            return processed_data

        except Exception as e:
            raise EventProcessingError(f"Error processing event {event['transactionHash'].hex()}: {e}")


class CrossChainBridgeEventListener:
    """The main orchestrator for listening to, processing, and acting on bridge events."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.source_connector = BlockchainConnector(config['source_rpc'])
        self.dest_connector = BlockchainConnector(config['dest_rpc'])
        self.state_manager = StateManager()
        self.event_processor = EventProcessor(self.state_manager)
        self.source_contract = self.source_connector.get_contract(
            config['contract_address'],
            config['contract_abi']
        )
        self._last_processed_block = None

    def _get_start_block(self) -> int:
        """Determines the block number to start scanning from."""
        if self._last_processed_block:
            return self._last_processed_block + 1
        try:
            # On first run, start from a recent block to avoid scanning the whole chain.
            return self.source_connector.get_latest_block_number() - self.config['confirmations'] - 10
        except RPCConnectionError as e:
            logging.error(f"Cannot fetch latest block to start: {e}. Retrying...")
            return -1 # Sentinel value to indicate retry

    def _poll_and_process_events(self):
        """The core logic for a single polling iteration."""
        try:
            start_block = self._get_start_block()
            if start_block == -1: return

            # We scan up to a block that is considered 'confirmed'.
            latest_confirmed_block = self.source_connector.get_latest_block_number() - self.config['confirmations']

            if start_block > latest_confirmed_block:
                logging.debug(f"No new confirmed blocks to process. Current: {start_block-1}, Confirmed: {latest_confirmed_block}")
                return

            logging.info(f"Scanning for 'TokensLocked' events from block {start_block} to {latest_confirmed_block}...")

            # Fetch raw event logs
            raw_events = self.source_connector.get_events(
                self.source_contract,
                'TokensLocked',
                from_block=start_block,
                to_block=latest_confirmed_block
            )

            if not raw_events:
                logging.debug("No new events found in this range.")
            else:
                logging.info(f"Found {len(raw_events)} new raw event(s). Processing...")
                for event in sorted(raw_events, key=lambda e: (e['blockNumber'], e['logIndex'])):
                    try:
                        processed_event = self.event_processor.process_event(event)
                        if processed_event:
                            self.simulate_destination_chain_action(processed_event)
                            # Mark as processed after the action is successfully simulated.
                            event_id = f"{processed_event['tx_hash']}-{processed_event['log_index']}"
                            self.state_manager.mark_as_processed(event_id)

                    except (InvalidEventError, EventProcessingError) as e:
                        logging.error(f"Failed to process an event: {e}")

            # Update the last processed block *only if* the scan was successful.
            self._last_processed_block = latest_confirmed_block

        except RPCConnectionError as e:
            logging.error(f"RPC Connection Error during polling: {e}. Attempting to reconnect.")
            self.source_connector.connect() # Attempt to reconnect
        except Exception as e:
            logging.error(f"An unexpected error occurred in the polling loop: {e}")

    def simulate_destination_chain_action(self, event_data: Dict[str, Any]):
        """Simulates the action that would be taken on the destination chain.

        In a real bridge, this method would construct, sign, and broadcast a transaction
        on the destination chain (e.g., to a minting contract).
        """
        logging.info("--- SIMULATING DESTINATION CHAIN ACTION ---")
        logging.info(f"  Action: Mint tokens for recipient {event_data['recipient']}")
        logging.info(f"  Amount: {event_data['amount']} of token {event_data['token_address']}")
        logging.info(f"  Source Tx: {event_data['tx_hash']}")
        logging.info(f"  Nonce: {event_data['nonce']}")
        logging.info("  Status: Action would be sent to the destination chain relayer network.")
        logging.info("-------------------------------------------")

    def run(self):
        """Starts the main event listening loop."""
        logging.info("*** Cross-Chain Bridge Event Listener starting... ***")
        logging.info(f"Listening for 'TokensLocked' on contract: {self.config['contract_address']}")
        while True:
            try:
                self._poll_and_process_events()
                time.sleep(self.config['poll_interval'])
            except KeyboardInterrupt:
                logging.info("*** Shutting down listener... ***")
                break
            except Exception as e:
                # Catch-all for unexpected errors to keep the service running
                logging.critical(f"FATAL ERROR in main loop: {e}. Restarting loop after a delay.")
                time.sleep(self.config['poll_interval'] * 2)


if __name__ == '__main__':
    # Prepare the configuration dictionary
    app_config = {
        'source_rpc': SOURCE_CHAIN_RPC,
        'dest_rpc': DESTINATION_CHAIN_RPC,
        'contract_address': SOURCE_BRIDGE_CONTRACT_ADDRESS,
        'contract_abi': SOURCE_BRIDGE_CONTRACT_ABI,
        'confirmations': BLOCK_CONFIRMATIONS,
        'poll_interval': POLL_INTERVAL_SECONDS
    }

    listener = CrossChainBridgeEventListener(app_config)
    listener.run()



# @-internal-utility-start
def log_event_5543(event_name: str, level: str = "INFO"):
    """Logs a system event - added on 2025-10-30 12:53:44"""
    print(f"[{level}] - 2025-10-30 12:53:44 - Event: {event_name}")
# @-internal-utility-end

