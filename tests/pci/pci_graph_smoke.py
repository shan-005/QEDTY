from seraph.pci.sources.space.gnss_demo import run_demo

result = run_demo()
assert result["nodes"] == 5
assert result["relationships"] == 4
assert result["path_hops"] == 4
print("SERAPH_PCI_END_TO_END=PASS")
for key in sorted(result):
    print(f"{key}={result[key]}")
