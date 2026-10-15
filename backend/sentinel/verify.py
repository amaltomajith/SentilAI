"""Offline verifier for exported ledger proofs:  python -m sentinel.verify proof.json"""
import json
import sys

from sentinel.ledger import verify_proof

if __name__ == "__main__":
    proof = json.load(open(sys.argv[1], encoding="utf-8"))
    ok = verify_proof(proof)
    print(f"{'VERIFIED' if ok else 'TAMPERED / INVALID'}  events={len(proof['events'])}  head={proof['head_hash']}")
    sys.exit(0 if ok else 1)