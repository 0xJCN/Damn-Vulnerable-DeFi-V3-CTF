from ape import accounts, project
from .utils.helper import w3

TOKENS_IN_POOL = w3.to_wei(1000000, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n---\n"
    )

    # deploy token and lender contracts
    print("\n--- Deploying Token and Lender Contracts ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)
    pool = project.TrusterLenderPool.deploy(token.address, sender=deployer)
    assert pool.token() == token.address

    # transfer tokens to pool
    print("\n--- Funding Pool with tokens ---\n")
    token.transfer(pool.address, TOKENS_IN_POOL, sender=deployer)

    assert token.balanceOf(pool.address) == TOKENS_IN_POOL
    assert token.balanceOf(attacker.address) == 0

    # define intial balances for pool and attacker
    pool_initial_bal = token.balanceOf(pool.address) / 10**18
    attacker_initial_bal = token.balanceOf(attacker.address) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    attacker_contract = project.TrusterAttacker.deploy(
        pool.address, token.address, sender=attacker
    )
    attacker_contract.attack(sender=attacker)

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: attacker should have stolen all tokens from the pool ---\n"
    )

    # define ending balances for pool and attacker
    pool_ending_bal = token.balanceOf(pool.address) / 10**18
    attacker_ending_bal = token.balanceOf(attacker.address) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    assert token.balanceOf(attacker.address) == TOKENS_IN_POOL
    assert token.balanceOf(pool.address) == 0

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
