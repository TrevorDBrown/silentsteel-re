import nefile
steel = nefile.NE('C:\\Users\\Trevor Brown\\Desktop\\Silent Steel (1995)\\Disc Content\\Promotional\\STEEL.EXE')

print(steel.header.start_offset)
print(steel.header._resource_table_offset_from_header_start)
print(steel.header.resource_table_offset)
print(steel.header)
print(steel.resource_table.alignment_shift_count)

print(steel.resource_table.resource_type_tables.keys())
print(steel.resource_table.resource_type_tables["DATA"])
print(steel.resource_table.resources["DATA"])

data_resources = steel.resource_table.resources["DATA"]
print(data_resources)

for resource_id, resource in data_resources.items():
    data_str = resource.data.read().decode("ascii").rstrip("\x1a \x00") # there's padding

    print("%i: %s"%(resource_id,data_str) )

    with open("TextDump-MSTEEL.txt", "a") as f:
        f.write("%i: %s\n\n"%(resource_id,data_str))