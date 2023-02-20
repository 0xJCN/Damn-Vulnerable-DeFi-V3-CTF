from ape import accounts, project
from ..utils.helper import w3, get_code

DEPOSIT_ADDRESS = "0x9b6fb606a9f5789444c17768c6dfcf2f83563801"
DEPOSIT_TOKEN_AMOUNT = w3.to_wei(20000000, "ether")


def main():
    # --- before exploit --- #
    print("\n--- Setting up scenario ---\n")

    # get accounts
    deployer = accounts.test_accounts[0]
    attacker = accounts.test_accounts[1]
    ward = accounts.test_accounts[2]

    print(
        f"\n--- \nOur players:\n⇒ Deployer: {deployer}\n⇒ Attacker: {attacker}\n⇒ Ward: {ward}---\n"
    )

    # Deploy Token
    print("\n--- Deploying Token ---\n")
    token = project.DamnValuableToken.deploy(sender=deployer)

    # Deploy authorizer with the corresponding proxy
    print(
        "\n--- Deploying Authorizer Contract behind a proxy (using UUPS pattern) ---\n"
    )
    temp_authorizer = project.AuthorizerUpgradeable.deploy(sender=deployer)
    encoder = project.Encoder.deploy(sender=deployer)
    data = encoder.get_init_data([ward.address], [DEPOSIT_ADDRESS])
    proxy = project.ERC1967Proxy.deploy(temp_authorizer, data, sender=deployer)
    authorizer = project.AuthorizerUpgradeable.at(proxy)

    assert authorizer.owner() == deployer
    assert authorizer.can(ward, DEPOSIT_ADDRESS)
    assert not authorizer.can(attacker, DEPOSIT_ADDRESS)

    # Deploy safe deployer contract
    wallet_deployer = project.WalletDeployer.deploy(token, sender=deployer)
    assert wallet_deployer.chief() == deployer
    assert wallet_deployer.gem() == token

    # Set authorizer in safe deployer
    wallet_deployer.rule(authorizer, sender=deployer)
    assert wallet_deployer.mom() == authorizer

    assert wallet_deployer.can(ward, DEPOSIT_ADDRESS)
    # assert not wallet_deployer.can(attacker.address, DEPOSIT_ADDRESS)
    # check with out

    # fund safe deployer with tokens
    initial_wallet_deployer_token_balance = wallet_deployer.pay() * 43
    token.transfer(
        wallet_deployer,
        initial_wallet_deployer_token_balance,
        sender=deployer,
    )
    # ensure these accounts start empty
    assert get_code(DEPOSIT_ADDRESS) == "0x"
    assert get_code(wallet_deployer.fact()) == "0x"
    assert get_code(wallet_deployer.copy()) == "0x"

    # deposit large amount of DVT tokens to the Deposit Address
    print("\n--- Depositing tokens into Address ---\n")
    token.transfer(DEPOSIT_ADDRESS, DEPOSIT_TOKEN_AMOUNT, sender=deployer)

    # ensure initial balances are correctly set
    assert token.balanceOf(DEPOSIT_ADDRESS) == DEPOSIT_TOKEN_AMOUNT
    assert token.balanceOf(wallet_deployer) == initial_wallet_deployer_token_balance
    assert token.balanceOf(attacker) == 0

    # define initial balances for attacker and wallet
    address_initial_bal = token.balanceOf(DEPOSIT_ADDRESS) / 10**18
    attacker_initial_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nInitial Balances:\n⇒ Address: {address_initial_bal}\n⇒ Attacker: {attacker_initial_bal}\n---\n"
    )

    # --- EXPLOIT GOES HERE --- #
    print("\n--- Initiating exploit... ---\n")

    # exploit

    # --- AFTER EXPLOIT --- #
    print(
        "\n--- After exploit: Attacker has stolen all the tokens from the Address ---\n"
    )

    # define ending balances for attacker and wallet
    address_ending_bal = token.balanceOf(DEPOSIT_ADDRESS) / 10**18
    attacker_ending_bal = token.balanceOf(attacker) / 10**18

    print(
        f"\n--- \nEnding Balances:\n⇒ Address: {address_ending_bal}\n⇒ Attacker: {attacker_ending_bal}\n---\n"
    )

    # factory account must have code
    assert get_code(wallet_deployer.fact()) != "0x"

    # master copy must have code
    assert get_code(wallet_deployer.copy()) != "0x"

    # deposit account must have code
    assert get_code(DEPOSIT_ADDRESS) != "0x"

    # the deposit address and safe deployer contract must not hold tokens
    assert token.balanceOf(DEPOSIT_ADDRESS) == 0
    assert token.balanceOf(wallet_deployer) == 0

    # attacker must own all tokens
    assert (
        token.balanceOf(attacker)
        == initial_wallet_deployer_token_balance + DEPOSIT_TOKEN_AMOUNT
    )

    print("\n--- 🥂 Challenge Completed! 🥂---\n")


if __name__ == "__main__":
    main()
