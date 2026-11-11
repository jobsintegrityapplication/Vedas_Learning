# Profile-specific recitation audio

Kanchi and Sringeri reference assets are independent. `recitation_reference_audio` stores one full-mantra asset per profile/address and ordered word clip assets with timestamps, plus source URL/title, speaker and source attribution, rights state/notes, validation state/notes, technical metadata, and SHA-256. Asset upload starts with `validation_status=pending`; playback returns a presigned URL only when validation is `validated` and rights are `cleared` or `public_domain`. Missing, pending, rejected, link-only, restricted, or unknown-rights files are unavailable to learners.

Admin endpoints:

- `POST /api/recitation/admin/reference-audio` accepts multipart audio and source/profile/reference metadata. Use `asset_kind=full_mantra` for a complete mantra or `asset_kind=word` with `word_order`, `start_ms`, and `end_ms` for a word clip. Speaker attribution must be explicit (including “not identified” when the source provides none); it is never inferred.
- `POST /api/recitation/admin/reference-audio/{asset_id}/review` records rights and validation decisions.
- `GET /api/recitation/{RV.MM.SSS.VV}/audio?profile=Kanchi|Sringeri` returns the independently validated full asset and ordered word clips, with explicit availability states.

Learner uploads use `POST /api/recordings/evaluate` with `recitation_profile=Kanchi|Sringeri` and optional `mantra_reference`. Storage keys are profile-separated, and `GET /api/recitation/learner-recordings?profile=...` returns only the signed-in learner's recordings for that profile. Existing lesson-level reference audio remains legacy and is not treated as a Kanchi or Sringeri recording. The client profile selector uses the new profile-specific endpoint and clearly reports unavailable audio.

There is no TTS synthesis path for Vedic chanting. Reference audio must come from a source-backed human recording. No audio was available in this task to populate these tables, so the new pipeline starts empty and all profile/mantra combinations remain unavailable until assets are supplied and reviewed.
