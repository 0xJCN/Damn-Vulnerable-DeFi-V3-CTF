from ape import accounts, project
from .utils.helper import w3, time_travel

TOKENS_IN_LENDER_POOL = w3.to_wei(1000000, "ether")


def main():
    # --- BEFORE EXPLOIT --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    alice = accounts.test_accounts[2]
    bob = accounts.test_accounts[3]
    lucy = accounts.test_accounts[4]
    john = accounts.test_accounts[5]

    users = [alice, bob, lucy, john]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n⇒ Alice: {alice}"
    )
    print(f"⇒ Bob: {bob}\n⇒ Lucy: {lucy}\n⇒ John: {john}\n---\n")

    # deploy liquidityToken and flashLoanPool
    print("\n--- Deploying liquidity token and flash loan pool ---\n")
    liquidity_token = project.DamnValuableToken.deploy(sender=deployer)
    flash_loan_pool = project.FlashLoanerPool.deploy(
        liquidity_token.address, sender=deployer
    )

    # set initial token balance of pool offering flash loans
    print("\n--- Funding flash loan pool with liquidity tokens ---\n")
    liquidity_token.transfer(
        flash_loan_pool.address, TOKENS_IN_LENDER_POOL, sender=deployer
    )

    # deploy rewarderPool, rewarderToken, and accountingToken
    print("\n--- Deploying reward pool, reward token, and accounting token ---\n")
    rewarder_pool = project.TheRewarderPool.deploy(
        liquidity_token.address, sender=deployer
    )
    reward_token = project.RewardToken.at(rewarder_pool.rewardToken())
    accounting_token = project.AccountingToken.at(rewarder_pool.accountingToken())

    # check roles in accounting token
    assert accounting_token.owner() == rewarder_pool.address
    minter_role = accounting_token.MINTER_ROLE()
    snapshot_role = accounting_token.SNAPSHOT_ROLE()
    burner_role = accounting_token.BURNER_ROLE()
    assert accounting_token.hasAllRoles(
        rewarder_pool.address, minter_role | snapshot_role | burner_role
    )

    # users deposit 100 tokens each
    print(
        "\n--- Each user is depositing 100 liquidity tokens into the rewarder pool ---\n"
    )
    deposit_amount = w3.to_wei(100, "ether")
    for user in users:
        liquidity_token.transfer(user.address, deposit_amount, sender=deployer)
        liquidity_token.approve(rewarder_pool.address, deposit_amount, sender=user)
        rewarder_pool.deposit(deposit_amount, sender=user)
        assert accounting_token.balanceOf(user.address) == deposit_amount
        print(f"\n--- {user} has deposited into the pool ---\n")

    assert accounting_token.totalSupply() == deposit_amount * len(users)
    assert reward_token.totalSupply() == 0

    # advance time 5 days so that depositors can get rewards
    print("\n--- Advancing time 5 days into the future to claim rewards... ---\n")
    time_travel(5 * 24 * 60 * 60)

    # reward the users/depositors 25 reward tokens
    print(
        "\n--- ...5 days later the users are collecting their rewards from the pool ---\n"
    )
    rewards_in_round = rewarder_pool.REWARDS()
    for user in users:
        rewarder_pool.distributeRewards(sender=user)
        assert reward_token.balanceOf(user.address) == rewards_in_round / len(users)
        print(f"\n--- {user} has collected their reward tokens ---\n")

    assert reward_token.totalSupply() == rewards_in_round

    # assert attacker starts with 0 dvt tokens
    assert liquidity_token.balanceOf(attacker.address) == 0

    # two rounds must have occured so far
    assert rewarder_pool.roundNumber() == 2

    # define intial balances for users and attackers
    alice_initial_bal = reward_token.balanceOf(users[0].address) / 10**18
    bob_initial_bal = reward_token.balanceOf(users[1].address) / 10**18
    lucy_initial_bal = reward_token.balanceOf(users[2].address) / 10**18
    john_initial_bal = reward_token.balanceOf(users[3].address) / 10**18
    attacker_initial_bal = reward_token.balanceOf(attacker.address) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Alice: {alice_initial_bal}\n⇒ Bob: {bob_initial_bal}"
    )
    print(
        f"⇒ Lucy: {lucy_initial_bal}\n⇒ John: {john_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # wait 5 days until the next round
    time_travel(5 * 24 * 60 * 60)

    attacker_contract = project.TheRewarderAttacker.deploy(
        rewarder_pool.address,
        flash_loan_pool.address,
        liquidity_token.address,
        reward_token.address,
        sender=attacker,
    )
    attacker_contract.attack(sender=attacker)

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: Attacker should have claimed most of the rewards for themselves ---\n"
    )
    # only one round must have taken place
    assert rewarder_pool.roundNumber() == 3

    # users should get negligible rewards this round
    for user in users:
        rewarder_pool.distributeRewards(sender=user)
        # The difference between current and previous rewards balance should
        # be lower than 0.01 tokens
        user_rewards = reward_token.balanceOf(user.address)
        delta = user_rewards - (rewarder_pool.REWARDS() / len(users))
        assert delta < 10**16

    # define ending balances for users and attacker
    alice_ending_bal = reward_token.balanceOf(users[0].address) / 10**18
    bob_ending_bal = reward_token.balanceOf(users[1].address) / 10**18
    lucy_ending_bal = reward_token.balanceOf(users[2].address) / 10**18
    john_ending_bal = reward_token.balanceOf(users[3].address) / 10**18
    attacker_ending_bal = reward_token.balanceOf(attacker.address) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Alice: {alice_ending_bal}\n⇒ Bob: {bob_ending_bal}"
    )
    print(
        f"⇒ Lucy: {lucy_ending_bal}\n⇒ John: {john_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # check that rewards have been issued to attacker account
    assert reward_token.totalSupply() > rewarder_pool.REWARDS()
    attacker_rewards = reward_token.balanceOf(attacker.address)
    assert attacker_rewards > 0

    # the amount of rewards earned should be close to total available amount
    delta = rewarder_pool.REWARDS() - attacker_rewards
    assert delta < 10**17

    # Balance of DVT tokens in attacker and lending pool hasn't changed
    assert liquidity_token.balanceOf(attacker.address) == 0
    assert liquidity_token.balanceOf(flash_loan_pool.address) == TOKENS_IN_LENDER_POOL

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
