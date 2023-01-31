from ape import accounts, project
from .utils.helper import w3, set_balance, get_timestamp, ZERO_ADDRESS

# The NFT marketplace will have 6 tokens, at 15 ETH each
NFT_PRICE = w3.to_wei(15, "ether")
AMOUNT_OF_NFTS = 6
MARKETPLACE_INITIAL_ETH_BALANCE = w3.to_wei(90, "ether")

# attacker starts with 0.1 ETH
ATTACKER_INITIAL_ETH_BALANCE = w3.to_wei(0.1, "ether")

# The buyer will offer 45 ETH as a bounty for the job
BOUNTY = w3.to_wei(45, "ether")

# Initial reserves for the Uniswap v2 pool
UNISWAP_INITIAL_TOKEN_RESERVE = w3.to_wei(15000, "ether")
UNISWAP_INITIAL_WETH_RESERVE = w3.to_wei(9000, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    dev = accounts.test_accounts[2]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n⇒ Dev: {dev}\n---\n"
    )

    # Attacker starts with 0.5 ETH balance
    print("\n--- Setting initial balance of attacker to 0.5 ETH ---\n")
    set_balance(attacker.address, ATTACKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTACKER_INITIAL_ETH_BALANCE

    # Deploy WETH contract
    print("\n--- Deploying WETH contract ---\n")
    weth = project.WETH9.deploy(sender=deployer)

    # Deploy token to be traded against WETH in Uniswap v2
    print("\n--- Deploying a token to be traded against WETH in Uniswap V2 ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)

    # Deploy Uniswap Factory and Router
    print("\n--- Deploying Uniswap Factory and Router ---\n")
    uni_factory = project.UniswapV2Factory.deploy(ZERO_ADDRESS, sender=deployer)
    uni_router = project.UniswapV2Router02.deploy(
        uni_factory.address, weth.address, sender=deployer
    )

    # Approve tokens, and then create Uniswap v2 pair against WETH and add liquidity
    # Note that the function takes care of deploying the pair automatically
    print("\n--- Creating a Pair against WETH and adding Liquidity ---\n")
    token.approve(uni_router.address, UNISWAP_INITIAL_TOKEN_RESERVE, sender=deployer)
    uni_router.addLiquidityETH(
        token.address,
        UNISWAP_INITIAL_TOKEN_RESERVE,
        0,
        0,
        deployer.address,
        get_timestamp() * 2,
        value=UNISWAP_INITIAL_WETH_RESERVE,
        sender=deployer,
    )
    # get reference to the created uniswap pair
    uni_pair = project.UniswapV2Pair.at(
        uni_factory.getPair(token.address, weth.address)
    )
    assert uni_pair.token0() == weth.address
    assert uni_pair.token1() == token.address
    assert uni_pair.balanceOf(deployer.address) > 0

    # Deploy the marketplace and get the associated ERC721 token
    # The marketplace will automatically mint AMOUNT_OF_NFTS to the deployer (see `FreeRiderNFTMarketplace::constructor`)
    print("\n--- Deploying Marketplace and funding it with 90 ETH ---\n")
    marketplace = project.FreeRiderNFTMarketplace.deploy(
        AMOUNT_OF_NFTS, value=MARKETPLACE_INITIAL_ETH_BALANCE, sender=deployer
    )

    # Deploy NFT contract
    print("\n--- Deploying NFT contract ---\n")
    nft = project.DamnValuableNFT.at(marketplace.token())

    # Ensure deployer owns all minted NFTs and approve the marketplace to trade them
    print("\n--- Ensuring dpeloyer owns all minted NFTs ---\n")
    for id in range(AMOUNT_OF_NFTS):
        assert nft.ownerOf(id) == deployer.address

    nft.setApprovalForAll(marketplace.address, True, sender=deployer)

    # Open offers in the marketplace
    print("\n--- Opening offers in the marketplace ---\n")
    marketplace.offerMany([0, 1, 2, 3, 4, 5], [NFT_PRICE] * 6, sender=deployer)
    assert marketplace.offersCount() == 6

    # Deploy Dev's contract, adding the attacker as a beneficiary
    print("\n--- Buyer deploying their contract to purchase NFTs ---\n")
    dev_contract = project.FreeRiderRecovery.deploy(
        attacker.address,  # beneficiary
        nft.address,
        value=BOUNTY,
        sender=dev,
    )

    # define initial balances for marketplace and attacker
    marketplace_initial_bal = marketplace.balance / 10**18
    attacker_initial_bal = attacker.balance / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Marketplace: {marketplace_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    attacker_contract = project.FreeRiderAttacker.deploy(
        uni_factory.address,
        marketplace.address,
        weth.address,
        token.address,
        nft.address,
        dev_contract.address,
        sender=attacker,
    )
    attacker_contract.attack(NFT_PRICE, sender=attacker)

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: Attacker should have earned all ETH from the bounty ---\n"
    )

    # define ending balances for marketplace and attacker
    marketplace_ending_bal = marketplace.balance / 10**18
    attacker_ending_bal = attacker.balance / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Marketplace: {marketplace_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # the dev extracts all NFTs from its associated contract
    for tokenId in range(AMOUNT_OF_NFTS):
        nft.transferFrom(
            dev_contract.address,
            dev.address,
            tokenId,
            sender=dev,
        )
        assert nft.ownerOf(tokenId) == dev.address

    # exchange must have lost NFTs and ETH
    assert marketplace.offersCount() == 0
    assert marketplace.balance < MARKETPLACE_INITIAL_ETH_BALANCE

    # attacker must have earned all ETH from the bounty
    assert attacker.balance > BOUNTY
    assert dev_contract.balance == 0

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
