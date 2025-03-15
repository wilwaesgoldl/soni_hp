# soni_hp: Cross-Chain Bridge Event Listener Simulation

This repository contains a Python-based simulation of a critical component in a decentralized cross-chain bridge: the **Event Listener**. This script is designed as a robust, architecturally-sound service that monitors a bridge contract on a source blockchain, processes events, and simulates corresponding actions on a destination chain.

## Concept

A cross-chain bridge allows users to transfer assets or data from one blockchain (e.g., Ethereum) to another (e.g., Polygon). A common mechanism is the "lock-and-mint" model:

1.  **Lock**: A user deposits an asset (e.g., `USDC`) into a smart contract on the source chain.
2.  **Event Emission**: The smart contract locks the asset and emits an event (e.g., `TokensLocked`) containing details of the transaction (sender, recipient, amount, destination chain).
3.  **Listen**: Off-chain services, called listeners or relayers, constantly monitor the source chain for these specific events.
4.  **Validate & Relay**: Upon detecting a confirmed `TokensLocked` event, the listener validates it and relays the information to the destination chain.
5.  **Mint**: A corresponding smart contract on the destination chain receives this information and mints an equivalent amount of a wrapped token (e.g., `pUSDC`) for the recipient.

This script simulates the crucial **Step 3 and 4**, acting as the off-chain listener that ensures the bridge functions correctly and securely.

## Code Architecture

The script is designed with a clear separation of concerns, using distinct classes to handle different aspects of the process. This makes the system more modular, testable, and maintainable.

-   `CrossChainBridgeEventListener`
    -   **Role**: The main orchestrator. It manages the main application loop, coordinates all other components, and handles the high-level logic of polling for events.

-   `BlockchainConnector`
    -   **Role**: A wrapper around the `web3.py` library. It abstracts all direct blockchain interactions, such as connecting to an RPC node, fetching blocks, creating contract instances, and querying for event logs. Two instances of this class are used: one for the source chain and one for the destination chain.

-   `EventProcessor`
    -   **Role**: Responsible for the business logic of handling a raw event. It parses the event data, validates its integrity, and can enrich it with off-chain information (in this simulation, it fetches a token's price via a `requests` call to the CoinGecko API).

-   `StateManager`
    -   **Role**: Prevents the double-processing of events (replay attacks). It keeps track of the transaction hashes of events that have already been successfully processed. In this simulation, it's an in-memory set, but in a production system, it would be backed by a persistent database like Redis or PostgreSQL.

-   **Custom Exceptions**
    -   `RPCConnectionError`, `EventProcessingError`, `InvalidEventError`: These provide more specific error handling than generic exceptions, making the system's behavior easier to debug and understand.

### Architectural Flow

```
+---------------------------------+
| CrossChainBridgeEventListener   | (Orchestrator)
| - run()                         |
+----------------|----------------+
                 | Polls every N seconds
                 v
+----------------|----------------+
| BlockchainConnector (Source)    |
| - get_latest_block_number()     |
| - get_events()                  |
+----------------|----------------+
                 | Returns raw events
                 v
+----------------|----------------+
| EventProcessor                  |
| - process_event()               |<>---+ (Uses to check for duplicates)
|  - Parse                        |    |
|  - Validate                     |    | +--------------+
|  - Enrich (e.g., API call)      |    +-->| StateManager |
+----------------|----------------+      +--------------+
                 | Returns processed data
                 v
+---------------------------------+
| CrossChainBridgeEventListener   |
| - simulate_destination_action() |
| - Updates StateManager          |
+---------------------------------+
```

## How it Works

The listener operates in a continuous loop with the following steps:

1.  **Initialization**: The main `CrossChainBridgeEventListener` is instantiated. It creates instances of the blockchain connectors, state manager, and event processor.

2.  **Polling Block Range**: The script doesn't just ask for the latest events. It intelligently calculates a block range to scan. It starts from the last block it successfully processed and scans up to the latest block minus a `BLOCK_CONFIRMATIONS` buffer. This buffer is critical to mitigate the risk of processing events from blocks that might be reversed due to a chain re-organization (re-org).

3.  **Event Fetching**: Using the `BlockchainConnector`, it queries the source chain's bridge contract for any `TokensLocked` events within the calculated block range.

4.  **Processing**: If events are found, they are passed one-by-one to the `EventProcessor`:
    a.  **Replay Protection**: The `StateManager` is first checked to see if the event's unique identifier (a combination of transaction hash and log index) has been processed before. If so, it's ignored.
    b.  **Parsing & Validation**: The event's arguments (sender, amount, etc.) are extracted and checked for completeness.
    c.  **Data Enrichment**: An external API call is made to fetch the USD price of the transferred token, demonstrating how off-chain data can be integrated.

5.  **Action Simulation**: For each valid, new event, the script calls `simulate_destination_chain_action()`. This method logs a detailed message describing the transaction that *would* be created and sent to the destination chain to mint the new tokens.

6.  **State Update**: Once an event has been successfully processed and its corresponding action simulated, its identifier is saved in the `StateManager` to prevent it from being processed again.

7.  **Loop**: The script waits for a configurable `POLL_INTERVAL_SECONDS` and then repeats the process, ensuring continuous and up-to-date monitoring of the bridge.

## Usage Example

### 1. Setup the Environment

First, clone the repository and navigate into the directory:

```bash
git clone https://github.com/your-username/soni_hp.git
cd soni_hp
```

Create a Python virtual environment and activate it:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configuration

For a real deployment, you would create a `.env` file to store your RPC URLs. The script is configured to read these variables.

Create a file named `.env` in the root directory:

```
# .env file
SOURCE_CHAIN_RPC="https://your-sepolia-rpc-url.com"
DESTINATION_CHAIN_RPC="https://your-goerli-rpc-url.com"
```

> **Note**: The script contains public, placeholder RPC URLs. These may be rate-limited or unreliable. For serious use, replace them with your own private RPC endpoints from a service like Infura or Alchemy.

### 3. Run the Listener

Execute the script from your terminal:

```bash
python script.py
```

### 4. Sample Output

The script will start logging its activity to the console. You will see messages indicating its status, any events it finds, and the simulated actions.

```
2023-10-27 15:30:00 - [INFO] - *** Cross-Chain Bridge Event Listener starting... ***
2023-10-27 15:30:00 - [INFO] - Listening for 'TokensLocked' on contract: 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
2023-10-27 15:30:02 - [INFO] - Successfully connected to RPC endpoint: https://rpc.sepolia.org
2023-10-27 15:30:03 - [INFO] - Successfully connected to RPC endpoint: https://rpc.goerli.mudit.blog/
2023-10-27 15:30:03 - [INFO] - StateManager initialized (in-memory).
2023-10-27 15:30:03 - [INFO] - EventProcessor initialized.
2023-10-27 15:30:05 - [INFO] - Scanning for 'TokensLocked' events from block 4812300 to 4812315...
2023-10-27 15:30:06 - [DEBUG] - No new events found in this range.
2023-10-27 15:30:16 - [INFO] - Scanning for 'TokensLocked' events from block 4812316 to 4812317...
2023-10-27 15:30:18 - [INFO] - Found 1 new raw event(s). Processing...
2023-10-27 15:30:19 - [INFO] - Successfully processed event from tx 0x123abcde... nonce 101
2023-10-27 15:30:19 - [INFO] - --- SIMULATING DESTINATION CHAIN ACTION ---
2023-10-27 15:30:19 - [INFO] -   Action: Mint tokens for recipient 0xRecipientAddress...
2023-10-27 15:30:19 - [INFO] -   Amount: 1000000000000000000 of token 0xTokenAddress...
2023-10-27 15:30:19 - [INFO] -   Source Tx: 0x123abcde...fgh456
2023-10-27 15:30:19 - [INFO] -   Nonce: 101
2023-10-27 15:30:19 - [INFO] -   Status: Action would be sent to the destination chain relayer network.
2023-10-27 15:30:19 - [INFO] - -------------------------------------------
...
```