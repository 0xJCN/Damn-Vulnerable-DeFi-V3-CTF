# @version ^0.3.7

@external
@pure
def get_encoded(admin: address, proposer: address, sweeper: address) -> Bytes[100]:
    return _abi_encode(admin, proposer, sweeper, method_id=method_id("initialize(address,address,address)"))

@external
@pure
def get_init_data(ward: DynArray[address, 1], deposit_address: DynArray[address, 1]) -> Bytes[196]:
    return _abi_encode(ward, deposit_address, method_id=method_id("init(address[],address[])"))

@external
@pure
def get_role(role: String[32]) -> bytes32:
    return keccak256(role)
