"""Read-only access to databases Maple does not own (D18, ADR-0019).

Kept separate from Maple's writable storage: nothing here may write, migrate,
or reuse LifeRepository / DataDir. Sensors import only `interface`; the SQLite
implementation is chosen by runtime.
"""
