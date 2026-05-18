; ILLUSTRATIVE ONLY — opcode-fuzz v0.3.0 does NOT consume this
; file. gpl-asm v0.7.0 parses the full text-listing format
; (per-line `<offset>  <byte>  <mnemonic>  <params>`); the
; short-form mnemonics below need either a preprocessor in
; opcode-fuzz or a gpl-asm extension before they can encode.
; See recipes/README.md for the format-decision status.
;
; This file documents the *intent* of the byte-inc recipe so
; whichever short-form path lands first has a target shape.
;
; opcode-fuzz recipe: increment a sentinel GBYTE
;
; The simplest possible discovery loop. Pre-state: SENTINEL_GBYTE
; holds whatever value the engine left it at. The recipe
; increments the sentinel BEFORE the target opcode and AFTER, so
; the diff catches:
;
;   pre+1 = SENTINEL_GBYTE delta from prologue (always 1)
;   pre+2 = SENTINEL_GBYTE delta after target  (extra delta from
;           the target opcode, if any)
;
; Any change to other globals across the run is also attributable
; to the target opcode (the prologue and epilogue touch only
; SENTINEL_GBYTE; everything else is pristine).
;
; Parameters (opcode-fuzz fuzz prepends these):
;
;   %define TARGET_OPCODE_HEX 0x05
;   %define SENTINEL_GBYTE_ID 100

; Prologue: bump the sentinel.
gpl byte inc            GBYTE[SENTINEL_GBYTE_ID]

; Target opcode under test. db emits the literal byte; the
; engine's dispatcher consumes whatever parameters the handler
; reads. If the opcode reads N bytes, the next N bytes of this
; chunk become its arguments; the encoder pads with safe values.
db TARGET_OPCODE_HEX

; Padding bytes the target opcode may consume as arguments.
; Eight zero bytes covers every known opcode in the libgff
; table (max parameter byte count is well under 8).
db 0
db 0
db 0
db 0
db 0
db 0
db 0
db 0

; Epilogue: bump the sentinel again so the diff shows BOTH
; bumps as separate events.
gpl byte inc            GBYTE[SENTINEL_GBYTE_ID]

; Return to the engine's dispatch loop.
gpl global ret
