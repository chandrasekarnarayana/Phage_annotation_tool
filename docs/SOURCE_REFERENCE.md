# Source Reference



Generated from module, class, and function docstrings under `src/phage_annotator`.

Regenerate with `python scripts/generate_source_reference.py` after source-docstring changes.



## `phage_annotator`

Phage Annotator - Microscopy image annotation tool.

## `phage_annotator.__main__`

Entry point for `python -m phage_annotator`.

## `phage_annotator.algorithms`

Analysis algorithms and computational methods (Layer 3).

## `phage_annotator.algorithms.analysis`

Pure analysis helpers for background jobs (no Qt dependencies).

## `phage_annotator.algorithms.analysis_part1`

Extracted definitions group 1 for analysis.

Public documented symbols:
- `compute_mean_std` (function): Compute mean/std projections over T and Z dimensions.
- `compute_projections` (function): Compute multiple projections over the requested axes.
- `compute_projection` (function): Compute a single projection over the requested axes.
- `compute_roi_mean_for_path` (function): Load a TIFF and compute ROI mean on first frame.
- `compute_bleach_means` (function): Compute per-frame ROI mean over time for a (T, Z, Y, X) array.
- `apply_crop_rect` (function): Apply a rectangular crop to a 2D frame.
- `roi_mask_for_shape` (function): Return a boolean ROI mask for the given shape and ROI spec.
- `fit_bleach_curve` (function): Fit an exponential decay curve to ROI means.
- `map_point_to_crop` (function): Map a full-frame point into cropped coordinates.
- `roi_mask_for_polygon` (function): Return a polygon mask using matplotlib Path.
- `roi_mask_from_points` (function): Create an ROI mask from a generic ROI definition.
- `roi_mean_timeseries` (function): Compute ROI mean over time for a (T, Z, Y, X) array using Z=0.

## `phage_annotator.algorithms.analysis_part2`

Extracted definitions group 2 for analysis.

Public documented symbols:
- `roi_stats` (function): Compute mean/std/min/max and area for an ROI mask.
- `compute_auto_window` (function): Compute an auto-contrast window using percentile bounds.
- `mad_sigma` (function): Estimate noise sigma using the median absolute deviation (MAD).
- `local_maxima` (function): Return coordinates of local maxima above a threshold.
- `gaussian_2d` (function): Evaluate a symmetric 2D Gaussian on a meshgrid.
- `fit_gaussian_2d` (function): Fit a symmetric 2D Gaussian to a small patch.

## `phage_annotator.algorithms.auto_roi`

Auto ROI proposal for uniform, artifact-free regions.

Public documented symbols:
- `propose_roi` (function): Propose a ROI location with uniform illumination and minimal artifacts.

## `phage_annotator.algorithms.coordinate_transforms`

Backward compatibility facade for coordinate transforms.

## `phage_annotator.algorithms.deepstorm_infer`

Deep-STORM style ROI-only super-resolution reconstruction.

Public documented symbols:
- `DeepStormParams` (class): Parameters for Deep-STORM style inference.
- `DeepLocalization` (class): Localization extracted from a Deep-STORM SR image.
- `is_torch_available` (function): Return whether torch available is true for the current state.
- `load_model` (function): Load a TorchScript or state-dict model from disk.
- `run_deepstorm_stream` (function): Run Deep-STORM inference over a streamed frame iterator.
- `localizations_from_sr` (function): Extract approximate localizations from an SR image.

## `phage_annotator.algorithms.density_infer`

Tiled inference utilities for density prediction.

Public documented symbols:
- `DensityInferOptions` (class): Options for tiled density inference.
- `DensityResult` (class): Result bundle for density inference.
- `run_density_inference` (function): Run tiled density inference over an image with optional ROI/crop.

## `phage_annotator.algorithms.density_model`

Density model loader and predictor for 2D inputs.

Public documented symbols:
- `DensityPredictor` (class): Load and run a density map model on 2D images.

## `phage_annotator.algorithms.image_processing`

Image processing helpers (placeholder for future visualization work).

Public documented symbols:
- `load_image` (function): Load an image file.
- `save_image` (function): Save an image to disk.
- `annotate_image` (function): Placeholder for graphical annotation logic.

## `phage_annotator.algorithms.particles`

Particle analysis helpers for threshold masks (no Qt).

Public documented symbols:
- `Particle` (class): Particle measurement for a single connected component.
- `ParticleOptions` (class): Filter options for Analyze Particles.
- `analyze_particles` (function): Analyze connected components in a binary mask.

## `phage_annotator.algorithms.smlm_thunderstorm`

Classical SMLM localization pipeline inspired by ThunderSTORM.

Public documented symbols:
- `SmlmParams` (class): Parameters for the ThunderSTORM-style localization pipeline.
- `Localization` (class): Localization record for a single detection.
- `filter_frame` (function): Apply a band-pass filter to enhance spots.
- `detect_candidates` (function): Detect candidate peaks using local maxima and robust thresholding.
- `localize_candidates` (function): Refine candidate locations using 2D Gaussian fitting.
- `post_filter` (function): Apply uncertainty/brightness filtering and merge close detections.
- `merge_localizations` (function): Greedy merge of close localizations within the same frame.
- `render_sr_image` (function): Render a super-resolution image for the ROI region.
- `run_smlm_stream` (function): Run the SMLM pipeline over a frame stream.

## `phage_annotator.analysis`

Analysis and image processing (P3 refactoring).

## `phage_annotator.analysis.core`

Backward compatibility facade. Moved to phage_annotator.algorithms.analysis

## `phage_annotator.analysis.interactive_learning`

Interactive learning model inspired by Weka Trainable Segmentation.

## `phage_annotator.analysis.interactive_learning_model_part1`

Extracted method group 1 for InteractiveLearningModel.

Public documented symbols:
- `InteractiveLearningModelPart1` (class): Method group 1 extracted from InteractiveLearningModel.

## `phage_annotator.analysis.interactive_learning_model_part2`

Extracted method group 2 for InteractiveLearningModel.

Public documented symbols:
- `InteractiveLearningModelPart2` (class): Method group 2 extracted from InteractiveLearningModel.

## `phage_annotator.analysis.interactive_learning_part1`

Extracted definitions group 1 for interactive_learning.

Public documented symbols:
- `TrainingExample` (class): Single training example with features and label.

## `phage_annotator.analysis.interactive_learning_part2`

Extracted definitions group 2 for interactive_learning.

Public documented symbols:
- `InteractiveLearningModel` (class): Weka-inspired interactive learning for keypoint detection.

## `phage_annotator.analysis.local_peak_suggestion_model_part1`

Extracted method group 1 for LocalPeakSuggestionModel.

Public documented symbols:
- `LocalPeakSuggestionModelPart1` (class): Method group 1 extracted from LocalPeakSuggestionModel.

## `phage_annotator.analysis.local_peak_suggestion_model_part2`

Extracted method group 2 for LocalPeakSuggestionModel.

Public documented symbols:
- `LocalPeakSuggestionModelPart2` (class): Method group 2 extracted from LocalPeakSuggestionModel.

## `phage_annotator.analysis.local_peak_suggestion_model_part3`

Extracted method group 3 for LocalPeakSuggestionModel.

Public documented symbols:
- `LocalPeakSuggestionModelPart3` (class): Method group 3 extracted from LocalPeakSuggestionModel.

## `phage_annotator.analysis.local_peak_suggestion_model_part4`

Extracted method group 4 for LocalPeakSuggestionModel.

Public documented symbols:
- `LocalPeakSuggestionModelPart4` (class): Method group 4 extracted from LocalPeakSuggestionModel.

## `phage_annotator.analysis.local_peak_suggestion_model_part5`

Extracted method group 5 for LocalPeakSuggestionModel.

Public documented symbols:
- `LocalPeakSuggestionModelPart5` (class): Method group 5 extracted from LocalPeakSuggestionModel.

## `phage_annotator.analysis.particles`

Backward compatibility facade. Moved to phage_annotator.algorithms.particles

## `phage_annotator.analysis.qc_validators`

QC validators for annotation quality and problem detection.

## `phage_annotator.analysis.qc_validators_part1`

Extracted definitions group 1 for qc_validators.

Public documented symbols:
- `IssueSeverity` (class): Severity level for QC issues.
- `QCIssue` (class): A quality control issue detected in annotations.
- `DuplicateValidator` (class): Detects duplicate annotations (too close together).
- `OutOfBoundsValidator` (class): Detects annotations outside image bounds.
- `MissingLabelValidator` (class): Detects annotations with missing or inconsistent labels.

## `phage_annotator.analysis.qc_validators_part2`

Extracted definitions group 2 for qc_validators.

Public documented symbols:
- `DensityClusterValidator` (class): Detects suspicious density clusters.

## `phage_annotator.analysis.qc_validators_part3`

Extracted definitions group 3 for qc_validators.

Public documented symbols:
- `ImageArtifactValidator` (class): Detect broad image/stack artifact patterns using fast heuristics.

## `phage_annotator.analysis.qc_validators_part4`

Extracted definitions group 4 for qc_validators.

Public documented symbols:
- `PoissonConsistencyValidator` (class): Poisson/Fano-factor checks for image signal and annotation stochasticity.

## `phage_annotator.analysis.qc_validators_part5`

Extracted definitions group 5 for qc_validators.

Public documented symbols:
- `QCValidator` (class): Unified QC validator that runs all checks.

## `phage_annotator.analysis.reviewer_analytics`

Reviewer workflow analytics from audit and QC history.

Public documented symbols:
- `compute_reviewer_metrics` (function): Aggregate per-user workflow metrics from immutable audit events.
- `compute_issue_trend` (function): Return time-ordered QC issue snapshots from validation audit events.
- `build_reviewer_dashboard_text` (function): Build plain-text dashboard summary for quick review in GUI.

## `phage_annotator.analysis.suggestion_model`

Model-in-the-loop point suggestion adapters.

## `phage_annotator.analysis.suggestion_model_part1`

Extracted definitions group 1 for suggestion_model.

Public documented symbols:
- `SuggestionModel` (class): Interface for proposal models used by assisted annotation.

## `phage_annotator.analysis.suggestion_model_part2`

Extracted definitions group 2 for suggestion_model.

Public documented symbols:
- `LocalPeakSuggestionModel` (class): Fast baseline model using local maxima as candidate points.

## `phage_annotator.analysis.suggestion_model_part3`

Extracted definitions group 3 for suggestion_model.

Public documented symbols:
- `summarize_suggestion_feedback` (function): Compute simple acceptance summary for reporting.

## `phage_annotator.analysis.suggestion_ranker`

Lightweight proposal ranking and calibration for assisted annotation.

## `phage_annotator.analysis.suggestion_ranker_part1`

Extracted definitions group 1 for suggestion_ranker.

Public documented symbols:
- `calibration_bins` (function): Return reliability-style bin summaries for calibration monitoring.
- `expected_calibration_error` (function): Compute expected calibration error from reliability-style bins.
- `feature_vector_from_suggestion` (function): Extract stable numeric features from one proposal.
- `LightweightSuggestionRanker` (class): Simple logistic ranker with optional Platt-style calibration.

## `phage_annotator.analysis.suggestion_ranker_part2`

Extracted definitions group 2 for suggestion_ranker.

Public documented symbols:
- `dataset_metrics_from_suggestions` (function): Compute explicit proposal metrics for dashboarding.

## `phage_annotator.analysis.suggestion_rules`

Configurable cross-channel gating rules for assisted suggestions.

Public documented symbols:
- `load_suggestion_rule_config` (function): Load suggestion rule config for the current workflow.

## `phage_annotator.analysis.threshold`

Thresholding helpers for preview and masks (no Qt).

Public documented symbols:
- `PostprocessOptions` (class): Post-processing parameters for binary masks.
- `compute_threshold` (function): Compute a scalar threshold value for the given pixels.
- `make_mask` (function): Create a binary mask from a 2D image using low/high thresholds.
- `postprocess_mask` (function): Apply optional post-processing to a binary mask.
- `remove_small_objects` (function): Remove connected components smaller than min_area.
- `fill_holes` (function): Fill holes in a binary mask.
- `binary_open` (function): Binary opening with a disk footprint.
- `binary_close` (function): Binary closing with a disk footprint.
- `smooth_image` (function): Gaussian smoothing for threshold preview.
- `watershed_split` (function): Split touching blobs using distance-transform watershed.

## `phage_annotator.annotation`

Annotation system (P3 refactoring).

## `phage_annotator.annotation.core`

Backward compatibility facade for annotations module.

## `phage_annotator.annotation.index`

Backward compatibility facade for annotation index helpers.

## `phage_annotator.annotation.label_taxonomy`

Label taxonomy system for annotation management.

Public documented symbols:
- `LabelColor` (class): Standard colors for labels.
- `LabelDefinition` (class): Definition of a label/class.
- `LabelTaxonomy` (class): Hierarchical taxonomy of annotation labels.
- `create_default_taxonomy` (function): Create a default label taxonomy.

## `phage_annotator.annotation.metadata`

Backward compatibility facade for annotation metadata helpers.

## `phage_annotator.annotation.metadata_schema`

Metadata schema definitions and field type system for annotations.

Public documented symbols:
- `FieldType` (class): Metadata field data types.
- `FieldConstraint` (class): Constraints on a metadata field value.
- `FieldDefinition` (class): Definition of a single metadata field.
- `AnnotationMetadataSchema` (class): Schema definition for annotation metadata.
- `get_global_schema` (function): Get the global metadata schema instance.

## `phage_annotator.annotation.metadata_validator`

Metadata validation for annotations.

Public documented symbols:
- `MetadataValidator` (class): Validates metadata against schema.
- `validate_metadata` (function): Validate metadata using global schema.

## `phage_annotator.annotation.validation_error`

Validation error objects for annotation metadata checks.

Public documented symbols:
- `ValidationError` (class): Single validation error for a metadata field.

## `phage_annotator.cache`

Cache implementations and memory management (Layer 4).

## `phage_annotator.cache.array_pool`

Lightweight numpy array pooling for tile-sized buffers.

Public documented symbols:
- `PoolConfig` (class): Configuration for array pool behavior.
- `PoolStats` (class): Snapshot of array pool telemetry counters.
- `ArrayPool` (class): Reusable buffer pool keyed by (shape, dtype).
- `acquire_array` (function): Convenience wrapper for ARRAY_POOL.acquire.
- `release_array` (function): Convenience wrapper for ARRAY_POOL.release.

## `phage_annotator.cache.disk_cache`

Disk-based cache for evicted projection tiles.

## `phage_annotator.cache.disk_cache_load_part`

Async save completion and load methods for disk cache.

Public documented symbols:
- `DiskCachePart2` (class): Load and async-save completion methods for disk cache.

## `phage_annotator.cache.disk_cache_part1`

Extracted method group 1 for DiskCache.

Public documented symbols:
- `DiskCacheStats` (class): Statistics for disk cache performance.
- `DiskCacheConfig` (class): Configuration for disk cache.
- `CompressedBuffer` (class): Wrapper for compressed data with lazy decompression.
- `DiskCachePart1` (class): Method group 1 extracted from DiskCache.

## `phage_annotator.cache.disk_cache_part2`

Extracted definitions group 2 for disk_cache.

Public documented symbols:
- `DiskCache` (class): Disk-based LRU cache for projection tiles with async I/O.

## `phage_annotator.cache.disk_cache_part3`

Extracted method group 3 for DiskCache.

Public documented symbols:
- `DiskCachePart3` (class): Method group 3 extracted from DiskCache.

## `phage_annotator.cache.eviction_base`

Base protocol for cache eviction strategies.

Public documented symbols:
- `EvictionStrategy` (class): Abstract base class for cache eviction strategies.

## `phage_annotator.cache.fifo_strategy`

First-in-first-out cache eviction strategy.

Public documented symbols:
- `FIFOEvictionStrategy` (class): Evict the oldest entry regardless of access frequency.

## `phage_annotator.cache.lfu_strategy`

Least-frequently-used cache eviction strategy.

Public documented symbols:
- `LFUEvictionStrategy` (class): Evict the entry with the lowest access frequency.

## `phage_annotator.cache.lru_strategy`

Least-recently-used cache eviction strategy.

Public documented symbols:
- `LRUEvictionStrategy` (class): Evict the entry that was accessed longest ago.

## `phage_annotator.cache.projection_cache`

Projection LRU cache with a memory budget and eviction telemetry.

## `phage_annotator.cache.projection_cache_part1`

Extracted method group 1 for ProjectionCache.

Public documented symbols:
- `CacheItem` (class): Single cached array with its accounted byte size.
- `CacheTelemetry` (class): Cache hit/miss and eviction telemetry counters.
- `ProjectionCachePart2` (class): Compatibility placeholder for a previously generated method group.
- `ProjectionCachePart1` (class): Method group 1 extracted from ProjectionCache.

## `phage_annotator.cache.projection_cache_part2`

Extracted definitions group 2 for projection_cache.

Public documented symbols:
- `ProjectionCache` (class): LRU cache for projection arrays keyed by image/projection/crop/selection.

## `phage_annotator.cache.projection_cache_part3`

Extracted method group 3 for ProjectionCache.

Public documented symbols:
- `ProjectionCachePart3` (class): Method group 3 extracted from ProjectionCache.

## `phage_annotator.cache.strategies`

Compatibility exports for cache eviction strategy implementations.

## `phage_annotator.cache.strategy_registry`

Registry for cache eviction strategy factories.

Public documented symbols:
- `CacheStrategies` (class): Registry for cache eviction strategies.

## `phage_annotator.cli`

Command-line interface for the phage-annotator microscopy GUI.

Public documented symbols:
- `main` (function): Launch the Matplotlib+Qt keypoint annotation GUI for microscopy stacks.

## `phage_annotator.config`

Application configuration management.

## `phage_annotator.config.density`

Configuration dataclasses for density prediction models.

Public documented symbols:
- `DensityConfig` (class): Normalization and output settings for density prediction.

## `phage_annotator.config.performance`

Performance service level objectives (SLOs) for baseline datasets.

Public documented symbols:
- `PerformanceSLO` (class): Targets for navigation and redraw latency on reference datasets.

## `phage_annotator.config.settings`

Configuration helpers for phage-annotator.

Public documented symbols:
- `ComponentMemoryBudget` (class): Per-component memory budget (P7e).
- `AppConfig` (class): Runtime settings for microscopy keypoint annotation.

## `phage_annotator.constants`

Centralized application constants.

## `phage_annotator.constants.settings`

Application settings keys and default values.

Public documented symbols:
- `get_default` (function): Return the configured default for a settings key.

## `phage_annotator.core`

Core domain models and data structures - Layer 1: Core Models.

## `phage_annotator.core.annotation`

Keypoint models and serialization helpers for microscopy annotations.

## `phage_annotator.core.annotation_part1`

Extracted definitions group 1 for annotation.

## `phage_annotator.core.annotation_part1_part1`

Extracted definitions group 1 for annotation_part1.

Public documented symbols:
- `normalize_annotation_meta` (function): Normalize metadata dict to include baseline schema fields.
- `Keypoint` (class): Represents a single annotated point in a stack.
- `keypoints_to_dataframe` (function): Convert keypoints to a pandas DataFrame with standard columns.
- `save_keypoints_csv` (function): Write keypoints to CSV with standard columns.
- `save_keypoints_json` (function): Write keypoints to JSON grouped by image_name.

## `phage_annotator.core.annotation_part1_part2`

Extracted definitions group 2 for annotation_part1.

Public documented symbols:
- `keypoints_from_csv` (function): Load keypoints from a CSV file.
- `keypoints_from_json` (function): Load keypoints from a JSON file keyed by image_name.

## `phage_annotator.core.annotation_part2`

Extracted definitions group 2 for annotation.

Public documented symbols:
- `PointSuggestion` (class): Model-generated candidate point pending user decision.

## `phage_annotator.core.multi_modality`

Multi-modality annotation filtering and propagation utilities (

Public documented symbols:
- `filter_by_modality` (function): Filter annotations by modality index.
- `propagate_to_modality` (function): Create copies of annotations assigned to a target modality.
- `assign_to_modality` (function): Assign annotations to a specific modality (in-place modification).
- `get_modality_summary` (function): Get annotation counts per modality.

## `phage_annotator.core.rollout`

Feature-flag and baseline instrumentation helpers.

Public documented symbols:
- `normalize_feature_flags` (function): Return a normalized feature-flag payload with stable defaults.
- `default_workflow_metrics` (function): Create a fresh baseline workflow-metrics payload.
- `record_workflow_event` (function): Return updated workflow metrics after applying one event.
- `update_provenance_coverage` (function): Return workflow metrics updated with provenance coverage counts.

## `phage_annotator.core.session_state`

Dataclasses describing session, view, and image state.

Public documented symbols:
- `RoiSpec` (class): ROI specification in full-resolution coordinates.
- `ViewState` (class): View-specific state for the active session.
- `ImageState` (class): Image metadata tracked by the session.
- `SessionState` (class): Project/session state that persists across views.

## `phage_annotator.core.workspace_snapshot`

Central workspace snapshot model with explicit 3-layer state.

## `phage_annotator.core.workspace_snapshot_part1`

Extracted definitions group 1 for workspace_snapshot.

Public documented symbols:
- `apply_workspace_snapshot_to_controller` (function): Restore supported workspace fields onto controller state.

## `phage_annotator.core.workspace_snapshot_part2`

Extracted definitions group 2 for workspace_snapshot.

Public documented symbols:
- `ProjectLayerState` (class): Project-file layer: persistent project identity and file context.
- `SessionWorkspaceLayerState` (class): Session/workspace layer: active GUI/session state for exact restore.
- `SettingsPreferencesLayerState` (class): Preferences layer: app-wide settings and defaults.
- `WorkspaceSnapshot` (class): Top-level snapshot with explicit 3-layer model.
- `workspace_layer_registry` (function): List canonical tracked keys by layer.
- `build_workspace_snapshot` (function): Build a full 3-layer snapshot from controller + settings payload.
- `extract_ui_workspace_state` (function): Return UI workspace payload from snapshot, if present.

## `phage_annotator.data`

Data models and image handling (Layer 2).

## `phage_annotator.data.channel_display`

Per-channel display settings for multi-channel image viewing.

Public documented symbols:
- `BlendMode` (class): Blend modes for compositing multiple channels.
- `ChannelDisplayState` (class): Display state for a single channel.
- `MultiChannelDisplaySettings` (class): Container for multi-channel display state.

## `phage_annotator.data.display_mapping`

Display mapping utilities for non-destructive brightness/contrast control.

Public documented symbols:
- `DisplayMapping` (class): Brightness/contrast mapping state.
- `mapping_to_dict` (function): Serialize a DisplayMapping (no recursive dicts).
- `mapping_from_dict` (function): Deserialize a DisplayMapping.

## `phage_annotator.data.display_norm`

Matplotlib normalization helpers for display mappings.

Public documented symbols:
- `build_norm` (function): Return a matplotlib normalization for the display mapping.

## `phage_annotator.data.mock_data_source_part1`

Extracted method group 1 for MockDataSource.

Public documented symbols:
- `MockDataSourcePart1` (class): Method group 1 extracted from MockDataSource.

## `phage_annotator.data.mock_data_source_part2`

Extracted method group 2 for MockDataSource.

Public documented symbols:
- `MockDataSourcePart2` (class): Method group 2 extracted from MockDataSource.

## `phage_annotator.data.mock_ds`

Mock data sources for testing render/data separation.

Public documented symbols:
- `MockDataSource` (class): Simple mock data source for testing.

## `phage_annotator.data.models`

Lightweight image metadata containers used by the GUI.

Public documented symbols:
- `LazyImage` (class): Metadata and lazy-loaded array for a single image.

## `phage_annotator.data.pyramid`

Multi-resolution pyramid helpers for large 2D frames.

Public documented symbols:
- `pyramid_level_factor` (function): Return the integer downsample factor for a pyramid level.
- `downsample_mean_pool` (function): Downsample a 2D frame using mean pooling.

## `phage_annotator.data.ring_buffer`

Thread-safe ring buffer and block prefetcher for playback.

Public documented symbols:
- `BufferStats` (class): Snapshot of ring buffer occupancy.
- `FrameRingBuffer` (class): Thread-safe ring buffer for sequential playback frames.
- `BlockPrefetcher` (class): Background prefetcher that reads contiguous frame blocks.

## `phage_annotator.data.session_data_source_part1`

Extracted method group 1 for SessionDataSource.

Public documented symbols:
- `SessionDataSourcePart1` (class): Method group 1 extracted from SessionDataSource.

## `phage_annotator.data.session_data_source_part2`

Extracted method group 2 for SessionDataSource.

Public documented symbols:
- `SessionDataSourcePart2` (class): Method group 2 extracted from SessionDataSource.

## `phage_annotator.data.session_ds`

SessionDataSource adapter for render/data separation.

Public documented symbols:
- `SessionDataSource` (class): Data source adapter wrapping SessionController.

## `phage_annotator.data.sources`

Data source interfaces for render/data separation.

## `phage_annotator.data.sources_part1`

Extracted definitions group 1 for sources.

Public documented symbols:
- `ImageFrame` (class): A single 2D image frame with metadata.
- `Projection` (class): A computed projection (mean, std, max, etc.).
- `Annotation` (class): A single annotation point with metadata.
- `Calibration` (class): Pixel size calibration metadata.
- `DataSource` (class): Base interface for all data sources.

## `phage_annotator.data.sources_part2`

Extracted definitions group 2 for sources.

Public documented symbols:
- `ImageDataSource` (class): Interface for image frame and projection data.
- `AnnotationDataSource` (class): Interface for annotation overlay data.
- `OverlayDataSource` (class): Interface for generic overlay data (ROI, particles, etc.).
- `CalibratedDataSource` (class): Interface for calibration metadata.

## `phage_annotator.data.sources_part3`

Extracted definitions group 3 for sources.

Public documented symbols:
- `ComprehensiveDataSource` (class): Base class for data sources implementing all interfaces.

## `phage_annotator.deepstorm`

DeepStorm neural network module (P3 refactoring).

## `phage_annotator.deepstorm.infer`

Backward compatibility facade. Moved to phage_annotator.algorithms.deepstorm_infer

## `phage_annotator.deepstorm.widget`

Backward compatibility facade for deepstorm_widget.

## `phage_annotator.demo`

Utilities to generate dummy microscopy images and run a quick demo.

## `phage_annotator.demo_part1`

Extracted definitions group 1 for demo.

## `phage_annotator.demo_part2`

Extracted definitions group 2 for demo.

Public documented symbols:
- `generate_dummy_image` (function): Create a dummy TIFF/OME-TIFF image on disk for testing or demo.
- `run_demo` (function): Generate a dummy image and open it in the GUI.

## `phage_annotator.demo_part3`

Extracted definitions group 3 for demo.

Public documented symbols:
- `DummyImageArtifacts` (class): Backward-compatible return wrapper for generated demo assets.

## `phage_annotator.density`

Density estimation module (P3 refactoring).

## `phage_annotator.density.config`

Backward compatibility facade for density_config.

## `phage_annotator.density.infer`

Backward compatibility facade. Moved to phage_annotator.algorithms.density_infer

## `phage_annotator.density.model`

Backward compatibility facade. Moved to phage_annotator.algorithms.density_model

## `phage_annotator.framework`

Framework and service infrastructure (Layer 5).

## `phage_annotator.framework.base`

Compatibility exports for UI-agnostic framework service contracts.

## `phage_annotator.framework.cache_interface`

Cache-service interface contracts.

Public documented symbols:
- `CacheService` (class): Cache coordination and telemetry.

## `phage_annotator.framework.command`

Command system for application commands and actions.

Public documented symbols:
- `Command` (class): Base class for application commands.
- `CommandRegistration` (class): Registration info for a command.
- `CommandRegistry` (class): Registry for managing and executing commands.
- `get_registry` (function): Get the default global command registry.
- `set_registry` (function): Set the global command registry.

## `phage_annotator.framework.context`

Application context - central service container.

Public documented symbols:
- `ApplicationContext` (class): Central service container for the application.
- `get_event_service` (function): Get the global event service.
- `get_log_service` (function): Get the global log service.
- `get_settings_service` (function): Get the global settings service.
- `get_thread_service` (function): Get the global thread service.
- `get_cache_service` (function): Get the global cache service.

## `phage_annotator.framework.context_config`

Configuration model for application context initialization.

Public documented symbols:
- `ContextConfig` (class): Configuration for ApplicationContext initialization.

## `phage_annotator.framework.default_cache_service`

Default cache registry service implementation.

Public documented symbols:
- `DefaultCacheService` (class): Simple cache registry and statistics collector.

## `phage_annotator.framework.default_event_service`

Default headless event service implementation.

Public documented symbols:
- `DefaultEventService` (class): Simple in-memory pub/sub implementation.

## `phage_annotator.framework.default_log_service`

Default headless logging service implementation.

Public documented symbols:
- `DefaultLogService` (class): Simple logging service using Python's logging module.

## `phage_annotator.framework.default_service_registry`

Default service registry implementation.

Public documented symbols:
- `DefaultServiceRegistry` (class): Simple service registry backed by dict.

## `phage_annotator.framework.default_settings_service`

Default in-memory settings service implementation.

Public documented symbols:
- `DefaultSettingsService` (class): In-memory settings with optional file backing.

## `phage_annotator.framework.default_thread_service`

Default background thread service implementation.

Public documented symbols:
- `DefaultThreadService` (class): Thread pool service using concurrent.futures.ThreadPoolExecutor.

## `phage_annotator.framework.event_interface`

Event data and event-service interface contracts.

Public documented symbols:
- `Event` (class): Base class for all events on the event bus.
- `EventService` (class): Publish/subscribe event bus for loose coupling.

## `phage_annotator.framework.events`

Application events for service integration.

Public documented symbols:
- `ApplicationEvent` (class): Base class for all application events.
- `AnnotationChangedEvent` (class): Published when annotations are added, removed, or modified.
- `ViewStateChangedEvent` (class): Published when view state changes (T, Z, ROI, crop, display mapping).
- `CacheInvalidationEvent` (class): Published when caches should be cleared or invalidated.
- `SettingsChangedEvent` (class): Published when settings change.
- `RenderingStartedEvent` (class): Published when rendering starts (frame being processed).
- `RenderingCompletedEvent` (class): Published when rendering completes.
- `FileOpenedEvent` (class): Published when a file/project is opened.
- `FileClosedEvent` (class): Published when a file/project is closed.

## `phage_annotator.framework.jobs`

Compatibility layer exposing the Qt job manager from framework namespace.

## `phage_annotator.framework.log_interface`

Log-service interface contracts.

Public documented symbols:
- `LogLevel` (class): Log severity levels.
- `LogService` (class): Structured logging interface for headless operation.

## `phage_annotator.framework.plugin`

Plugin discovery, loading, and lifecycle management.

Public documented symbols:
- `Plugin` (class): Base class for application plugins.
- `PluginMetadata` (class): Plugin metadata loaded from entry point.
- `PluginManager` (class): Manages plugin discovery, loading, and lifecycle.
- `get_plugin_manager` (function): Get the default global plugin manager.
- `set_plugin_manager` (function): Set the global plugin manager.

## `phage_annotator.framework.registry_interface`

Service-registry interface contracts.

Public documented symbols:
- `ServiceRegistry` (class): Registry for looking up services by type.

## `phage_annotator.framework.services`

Compatibility exports for default framework service implementations.

## `phage_annotator.framework.settings_interface`

Settings-service interface contracts.

Public documented symbols:
- `SettingsService` (class): Configuration/preferences interface.

## `phage_annotator.framework.stale_result_guard`

Stale-result protection for background job callbacks.

Public documented symbols:
- `gen_job_id` (function): Generate a unique job ID.
- `store_current_job_id` (function): Register the given job ID as the current active job for this type.
- `is_current_job` (function): Check if the given job ID matches the current active job.
- `clear_job_id` (function): Clear the current active job ID for this type.

## `phage_annotator.framework.thread_interface`

Thread-service interface contracts.

Public documented symbols:
- `ThreadService` (class): Thread pool and async execution service.

## `phage_annotator.io`

I/O package for image, metadata, and project helpers.

## `phage_annotator.io.csv_metadata_io`

Enhanced CSV serialization with full metadata preservation.

Public documented symbols:
- `save_keypoints_csv_with_metadata` (function): Write keypoints to CSV preserving full metadata.
- `load_keypoints_csv_with_metadata` (function): Load keypoints from CSV with metadata preservation.

## `phage_annotator.io.data`

I/O-related data utilities.

## `phage_annotator.io.data.calibration`

Calibration helpers for pixel size and unit conversions.

Public documented symbols:
- `CalibrationState` (class): Resolved calibration state for an image.
- `resolve_calibration` (function): Resolve pixel size in um/px using metadata, user, or project defaults.

## `phage_annotator.io.data.transforms`

Central, testable coordinate transformation utilities.

Public documented symbols:
- `crop_to_full` (function): Convert cropped display coordinates to full image coordinates.
- `full_to_crop` (function): Convert full image coordinates to cropped display coordinates.
- `full_to_display` (function): Convert full-resolution coordinates to display (downsampled) coordinates.
- `display_to_full` (function): Convert display (downsampled) coordinates to full-resolution coordinates.
- `canvas_to_display` (function): Convert matplotlib canvas coordinates to image display coordinates.
- `display_to_canvas` (function): Convert image display coordinates to matplotlib canvas coordinates.
- `crop_rect_intersection` (function): Clip crop rectangle to image bounds.
- `roi_rect_in_display_coords` (function): Convert a full-resolution ROI rect to display coordinates.

## `phage_annotator.io.io_annotations`

Backward compatibility facade for annotation CSV readers.

## `phage_annotator.io.metadata`

Metadata indexing and parsing utilities.

## `phage_annotator.io.metadata.annotation`

Parse and format annotation metadata from filenames and files.

Public documented symbols:
- `parse_filename_tokens` (function): Parse annotation metadata tokens embedded in a filename.
- `parse_csv_header_meta` (function): Parse metadata JSON from CSV comment headers.
- `parse_json_meta` (function): Parse metadata from a JSON annotation file.
- `merge_meta` (function): Merge metadata dicts, preferring file metadata.
- `format_tokens` (function): Format metadata into filename tokens (without extension).

## `phage_annotator.io.metadata.index`

Annotation file indexing and matching helpers.

Public documented symbols:
- `AnnotationIndexEntry` (class): Metadata about an annotation file on disk.
- `build_index` (function): Scan a folder and index annotation files by normalized basename.
- `match` (function): Return annotation entries that match an image path.

## `phage_annotator.io.metadata.reader`

Metadata extraction for TIFF/OME/Micro-Manager images.

Public documented symbols:
- `MetadataBundle` (class): Container for raw and parsed metadata.
- `read_metadata` (function): Read metadata for a TIFF/OME-TIFF without loading pixel data.
- `read_metadata_summary` (function): Read a summary metadata dict without parsing full raw tags.

## `phage_annotator.io.metadata_reader`

Backward compatibility facade for metadata reader helpers.

## `phage_annotator.io.projects`

Project/session I/O helpers.

## `phage_annotator.io.projects.base`

Project/session I/O helpers for Phage Annotator.

Public documented symbols:
- `migrate_project_payload` (function): Upgrade project payloads to the latest schema version in-place.
- `save_project` (function): Write project JSON and save per-image annotations. Preserves axis overrides.
- `load_project` (function): Load project JSON. Returns images, settings, annotation/ROI/threshold/particle/import maps, modality_manager, channel_display_settings.

## `phage_annotator.io.projects.project_io`

Backward compatibility facade for project I/O helpers.

## `phage_annotator.io.qc_export`

QC report export functionality.

Public documented symbols:
- `QCReportExporter` (class): Export QC issues to various formats.

## `phage_annotator.io.readers`

Image and annotation readers.

## `phage_annotator.io.readers.annotations`

Helpers for loading annotations from multiple CSV formats.

Public documented symbols:
- `detect_format` (function): Detect CSV format (thunderstorm | legacy | other).
- `parse_legacy_csv` (function): Parse legacy CSVs containing only x/y.
- `parse_thunderstorm_csv` (function): Parse ThunderSTORM CSV into normalized keypoints.

## `phage_annotator.io.readers.base`

TIFF/OME-TIFF loading and axis normalization utilities.

## `phage_annotator.io.readers.base_part1`

Extracted definitions group 1 for base.

Public documented symbols:
- `parse_axes_info` (function): Parse axes metadata into a normalized axis info dictionary.

## `phage_annotator.io.readers.base_part2`

Extracted definitions group 2 for base.

Public documented symbols:
- `ImageMeta` (class): Container for a loaded image stack standardized to (T, Z, Y, X).
- `standardize_axes` (function): Standardize an array to (T, Z, Y, X) and report time/Z presence.
- `load_images` (function): Load TIFF/OME-TIFF stacks, standardize axes, and wrap in ImageMeta.
- `read_contiguous_block_from_path` (function): Read a contiguous block of frames from disk and standardize axes.

## `phage_annotator.io.readers.base_part3`

Extracted definitions group 3 for base.

Public documented symbols:
- `read_contiguous_block` (function): Return a contiguous block (T slice) from a standardized (T, Z, Y, X) array.
- `read_metadata_bundle` (function): Read full metadata bundle from a TIFF/OME-TIFF.
- `read_metadata_summary` (function): Read a summary metadata dict without parsing full raw tags.

## `phage_annotator.io.standard_exports`

Standardized export adapters for interoperability and review workflows.

Public documented symbols:
- `validate_keypoints_for_export` (function): Return validation errors for export preflight.
- `export_canonical_csv` (function): Export keypoints with stable, explicit fields suitable for pipelines.
- `export_canonical_json` (function): Export keypoints in a deterministic canonical JSON envelope.
- `export_coco_keypoints` (function): Export a simple COCO keypoints-style payload.
- `export_evidence_bundle` (function): Write a review evidence bundle directory and return its manifest path.

## `phage_annotator.plugins`

Plugin space for extending the application (Layer 7).

## `phage_annotator.rendering`

Rendering and visualization (P3 refactoring).

## `phage_annotator.rendering.lut`

Backward compatibility facade for LUT helpers.

## `phage_annotator.rendering.mpl`

Matplotlib rendering helpers decoupled from the main window.

## `phage_annotator.rendering.mpl_part1`

Extracted definitions group 1 for mpl.

Public documented symbols:
- `RenderContext` (class): Render inputs for image panels and overlays.

## `phage_annotator.rendering.mpl_part2`

Extracted definitions group 2 for mpl.

Public documented symbols:
- `Renderer` (class): Renderer responsible for figure layout and artist updates.

## `phage_annotator.rendering.mpl_part3`

Extracted definitions group 3 for mpl.

## `phage_annotator.rendering.orthoview`

Backward compatibility facade for orthoview widget.

## `phage_annotator.rendering.renderer_part1`

Extracted method group 1 for Renderer.

Public documented symbols:
- `RendererPart1` (class): Method group 1 extracted from Renderer.

## `phage_annotator.rendering.renderer_part2`

Extracted method group 2 for Renderer.

Public documented symbols:
- `RendererPart2` (class): Method group 2 extracted from Renderer.

## `phage_annotator.rendering.renderer_part3`

Extracted method group 3 for Renderer.

Public documented symbols:
- `RendererPart3` (class): Method group 3 extracted from Renderer.

## `phage_annotator.rendering.scalebar`

Scale bar geometry helpers for rendering.

Public documented symbols:
- `ScaleBarSpec` (class): Configuration for a scale bar overlay.
- `compute_scalebar` (function): Compute scale bar geometry in data coordinates.

## `phage_annotator.roi`

ROI (Region of Interest) management (P3 refactoring).

## `phage_annotator.roi.auto`

Backward compatibility facade. Moved to phage_annotator.algorithms.auto_roi

## `phage_annotator.roi.commands`

Undo/redo commands for ROI Manager operations.

## `phage_annotator.roi.commands_part1`

Extracted definitions group 1 for commands.

Public documented symbols:
- `RoiCommandMemento` (class): Snapshot of ROI state for undo/redo.
- `RoiCommand` (class): Base class for undoable ROI commands.
- `AddRoiCommand` (class): Command to add a new ROI.
- `DeleteRoiCommand` (class): Command to delete an ROI.
- `RenameRoiCommand` (class): Command to rename an ROI.

## `phage_annotator.roi.commands_part2`

Extracted definitions group 2 for commands.

Public documented symbols:
- `UpdateRoiGeometryCommand` (class): Command to update ROI geometry.
- `SetRoiPositionCommand` (class): Command to set ROI position binding.
- `BatchDeleteRoisCommand` (class): Command to delete multiple ROIs.

## `phage_annotator.roi.commands_part3`

Extracted definitions group 3 for commands.

Public documented symbols:
- `AddTagCommand` (class): Command to add a tag to an ROI.
- `RemoveTagCommand` (class): Command to remove a tag from an ROI.

## `phage_annotator.roi.interactor`

Matplotlib ROI interactor for rectangle and circle ROIs.

## `phage_annotator.roi.interactor_part1`

Extracted definitions group 1 for interactor.

Public documented symbols:
- `CoordinateMapper` (class): Coordinate mapper between display and full-image space.

## `phage_annotator.roi.interactor_part2`

Extracted definitions group 2 for interactor.

Public documented symbols:
- `RoiInteractor` (class): Interactive ROI editor for a Matplotlib Axes.

## `phage_annotator.roi.manager`

ROI manager data model and JSON I/O with atomic, schema-versioned persistence.

## `phage_annotator.roi.manager_part1`

Extracted definitions group 1 for manager.

Public documented symbols:
- `Roi` (class): ROI definition in full-resolution coordinates.

## `phage_annotator.roi.manager_part2`

Extracted definitions group 2 for manager.

Public documented symbols:
- `RoiManager` (class): Manages ROIs per image, including templates for bulk operations.

## `phage_annotator.roi.manager_part3`

Extracted definitions group 3 for manager.

Public documented symbols:
- `roi_to_dict` (function): Convert ROI to dict for JSON serialization.
- `roi_from_dict` (function): Convert dict back to ROI with fallback for missing fields.
- `save_rois_json` (function): Save ROIs to JSON with atomic writes and auto-backup.
- `load_rois_json` (function): Load ROIs from JSON with schema validation.

## `phage_annotator.roi.roi_interactor_part1`

Extracted method group 1 for RoiInteractor.

Public documented symbols:
- `RoiInteractorPart1` (class): Method group 1 extracted from RoiInteractor.

## `phage_annotator.roi.roi_interactor_part2`

Extracted method group 2 for RoiInteractor.

Public documented symbols:
- `RoiInteractorPart2` (class): Method group 2 extracted from RoiInteractor.

## `phage_annotator.roi.widgets`

ROI Manager dock UI with Fiji-like interactions.

Public documented symbols:
- `RoiManagerWidget` (class): Dock widget for managing multiple ROIs with Fiji-parity controls.

## `phage_annotator.runtime`

Runtime startup checks and operational policy helpers.

## `phage_annotator.runtime.environment_check`

Startup validation for the `project/environment.yml` manifest.

Public documented symbols:
- `EnvironmentRequirement` (class): A single dependency requirement extracted from project/environment.yml.
- `EnvironmentCheckResult` (class): Result of comparing the active runtime with project/environment.yml.
- `check_environment` (function): Check the active Python environment against the project manifest.

## `phage_annotator.runtime.operational_policy`

Runtime policy for memory budgets and background responsiveness.

Public documented symbols:
- `RuntimeOperationalPolicy` (class): Bounded startup settings for responsive GUI operation.
- `build_runtime_policy` (function): Build startup limits for cache memory and background worker count.

## `phage_annotator.session`

Session management exports.

## `phage_annotator.session.annotation_io`

Annotation import/export, indexing, and merge helpers.

Public documented symbols:
- `SessionAnnotationIOMixin` (class): Mixin for annotation import/export, indexing, and merge helpers.

## `phage_annotator.session.annotations`

Annotation mutations and undo/redo helpers.

Public documented symbols:
- `SessionAnnotationsMixin` (class): Mixin for annotation mutations and undo/redo helpers.

## `phage_annotator.session.batch_commands`

Batch operation commands for QC issue resolution (M6).

## `phage_annotator.session.batch_commands_part1`

Extracted definitions group 1 for batch_commands.

Public documented symbols:
- `BatchAssignLabelCommand` (class): Command to assign labels to annotations missing labels.
- `BatchReviewDensityClustersCommand` (class): Command to mark density clusters as reviewed.

## `phage_annotator.session.batch_commands_part2`

Extracted definitions group 2 for batch_commands.

Public documented symbols:
- `BatchDeleteDuplicatesCommand` (class): Command to delete duplicate annotations identified by QC.
- `BatchDeleteOutOfBoundsCommand` (class): Command to delete out-of-bounds annotations identified by QC.

## `phage_annotator.session.commands`

Undo/redo command framework for view state changes.

## `phage_annotator.session.commands_part1`

Extracted definitions group 1 for commands.

Public documented symbols:
- `CommandMemento` (class): Snapshot of state for a command (P3.1).
- `Command` (class): Abstract base class for undoable commands (P3.1).
- `SetROICommand` (class): Command to change ROI (P3.1).
- `SetCropCommand` (class): Command to change crop region (P3.1).

## `phage_annotator.session.commands_part2`

Extracted definitions group 2 for commands.

Public documented symbols:
- `SetDisplayMappingCommand` (class): Command to change display mapping (vmin/vmax/gamma) (P3.1).
- `SetThresholdCommand` (class): Command to change threshold parameters (P3.1).

## `phage_annotator.session.commands_part3`

Extracted definitions group 3 for commands.

Public documented symbols:
- `command_from_dict` (function): Reconstruct a Command object from serialized data (P3.1).

## `phage_annotator.session.commands_part4`

Extracted definitions group 4 for commands.

Public documented symbols:
- `TransactionCommand` (class): Command that groups multiple sub-commands as a single transaction.

## `phage_annotator.session.context_commands`

Context annotation commands for near-point context actions.

## `phage_annotator.session.context_commands_part1`

Extracted definitions group 1 for context_commands.

Public documented symbols:
- `DeleteNearestCommand` (class): Command to delete the nearest annotation to a point.

## `phage_annotator.session.context_commands_part2`

Extracted definitions group 2 for context_commands.

Public documented symbols:
- `MarkUncertainCommand` (class): Command to mark nearest annotation as uncertain.
- `EditNearestMetadataCommand` (class): Command to update label/metadata on the nearest annotation.

## `phage_annotator.session.context_commands_part3`

Extracted definitions group 3 for context_commands.

Public documented symbols:
- `SnapToLocalMaxCommand` (class): Command to snap nearest annotation to local maximum.

## `phage_annotator.session.controller`

Session controller for application state mutations.

Public documented symbols:
- `SessionController` (class): Main state controller for the GUI.

## `phage_annotator.session.controller_annotation_commands`

Controller helpers exposing command-backed annotation and QC operations.

Public documented symbols:
- `SessionControllerAnnotationCommandsMixin` (class): Controller helpers for command-backed annotation updates and QC actions.

## `phage_annotator.session.controller_annotation_contexts`

Annotation-context ownership helpers for N-modality workflows.

Public documented symbols:
- `SessionControllerAnnotationContextsMixin` (class): Controller helpers for context-aware annotation ownership and bindings.

## `phage_annotator.session.controller_display`

Display-oriented controller helpers.

Public documented symbols:
- `SessionControllerDisplayMixin` (class): Controller helpers for display-related state.

## `phage_annotator.session.controller_preferences`

User and session preference controller helpers.

Public documented symbols:
- `SessionControllerPreferencesMixin` (class): Controller helpers for user/session preference state.

## `phage_annotator.session.controller_smlm`

SMLM-related controller helpers.

Public documented symbols:
- `SessionControllerSmlmMixin` (class): Controller helpers for persisted SMLM workflow state.

## `phage_annotator.session.controller_suggestions`

Suggestion workflow controller helpers.

Public documented symbols:
- `SessionControllerSuggestionsMixin` (class): Controller helpers for suggestion workflow, metrics, and training.

## `phage_annotator.session.controller_sync`

Controller helpers for lazy sync-group and ROI-sharing state.

Public documented symbols:
- `SessionControllerSyncMixin` (class): Controller APIs for lazy sync-group and sync-mode ownership.

## `phage_annotator.session.controller_threshold_particles`

Threshold, particles, and evidence-layer controller helpers.

Public documented symbols:
- `SessionControllerThresholdParticlesMixin` (class): Controller helpers for threshold, particles, and evidence-layer state.

## `phage_annotator.session.images`

Image loading, metadata, and calibration helpers for the session controller.

Public documented symbols:
- `SessionImageMixin` (class): Mixin for image loading, metadata, and calibration helpers.

## `phage_annotator.session.metadata_commands`

Commands for annotation metadata updates (undoable).

## `phage_annotator.session.metadata_commands_part1`

Extracted definitions group 1 for metadata_commands.

Public documented symbols:
- `UpdateMetadataCommand` (class): Command to update metadata for a single annotation.
- `BulkUpdateMetadataCommand` (class): Command to update metadata for multiple annotations.

## `phage_annotator.session.metadata_commands_part2`

Extracted definitions group 2 for metadata_commands.

Public documented symbols:
- `UpdateLabelCommand` (class): Command to change annotation label.

## `phage_annotator.session.migration`

Migration utilities for upgrading sessions to multi-modality support.

Public documented symbols:
- `upgrade_to_modalities` (function): Upgrade old primary/support session to use modalities.
- `downgrade_to_primary_support` (function): Downgrade modality-based session to primary/support (compatibility fallback).
- `ensure_modality_system` (function): Ensure session has a modality manager, creating if necessary.
- `get_active_modality_idx` (function): Get active (primary) modality index.
- `get_support_modality_idx` (function): Get support (secondary) modality index.
- `MigrationContext` (class): Context manager for safe migration operations.

## `phage_annotator.session.modality`

Multi-modality system: specification and management.

## `phage_annotator.session.modality_facade`

Backward-compatible facade for modality-based sessions.

Public documented symbols:
- `ModalityFacade` (class): Transparent facade bridging legacy primary/support with modalities.

## `phage_annotator.session.modality_manager_part1`

Extracted method group 1 for ModalityManager.

Public documented symbols:
- `ModalityManagerPart1` (class): Method group 1 extracted from ModalityManager.

## `phage_annotator.session.modality_manager_part2`

Extracted method group 2 for ModalityManager.

Public documented symbols:
- `ModalityManagerPart2` (class): Method group 2 extracted from ModalityManager.

## `phage_annotator.session.modality_part1`

Extracted definitions group 1 for modality.

Public documented symbols:
- `ProjectionType` (class): Types of projections that can be applied to image data.
- `ModalityDisplaySettings` (class): Display settings for a single modality.
- `ModalitySpec` (class): Specification for a single modality (image view).
- `ModalityLinks` (class): Synchronization links between modalities.

## `phage_annotator.session.modality_part2`

Extracted definitions group 2 for modality.

Public documented symbols:
- `ModalityManager` (class): Manager for multi-modality operations.

## `phage_annotator.session.modality_playback_manager_part1`

Extracted method group 1 for ModalityPlaybackManager.

Public documented symbols:
- `ModalityPlaybackManagerPart1` (class): Method group 1 extracted from ModalityPlaybackManager.

## `phage_annotator.session.modality_playback_manager_part2`

Extracted method group 2 for ModalityPlaybackManager.

Public documented symbols:
- `ModalityPlaybackManagerPart2` (class): Method group 2 extracted from ModalityPlaybackManager.

## `phage_annotator.session.modality_playback_manager_part3`

Extracted method group 3 for ModalityPlaybackManager.

Public documented symbols:
- `ModalityPlaybackManagerPart3` (class): Method group 3 extracted from ModalityPlaybackManager.

## `phage_annotator.session.multi_playback`

Multi-modality playback synchronization system.

## `phage_annotator.session.multi_playback_part1`

Extracted definitions group 1 for multi_playback.

Public documented symbols:
- `PlaybackMode` (class): Playback synchronization strategies.
- `ModalityPlaybackState` (class): Playback state for a single modality.

## `phage_annotator.session.multi_playback_part2`

Extracted definitions group 2 for multi_playback.

Public documented symbols:
- `ModalityPlaybackManager` (class): Manages playback synchronization across multiple modalities.

## `phage_annotator.session.navigation_commands`

Navigation commands for keyboard-first workflows.

Public documented symbols:
- `JumpToFrameCommand` (class): Command to jump to a specific time frame (T index).
- `JumpToZCommand` (class): Command to jump to a specific Z slice (depth index).

## `phage_annotator.session.playback`

Playback state handlers for the session controller.

Public documented symbols:
- `SessionPlaybackMixin` (class): Mixin for playback state handlers.

## `phage_annotator.session.project`

Project persistence compatibility shim.

Public documented symbols:
- `SessionProjectMixin` (class): Compatibility shim aggregating project persistence, bridge, and recovery mixins.

## `phage_annotator.session.project_bridge`

Project/session snapshot bridge and load/apply helpers.

Public documented symbols:
- `SessionProjectBridgeMixin` (class): Mixin for loading project payloads into controller/session state.

## `phage_annotator.session.project_export`

Annotation export metadata and file export helpers.

Public documented symbols:
- `SessionProjectExportMixin` (class): Mixin for annotation export metadata and file export helpers.

## `phage_annotator.session.project_persistence`

Project save/load persistence helpers.

Public documented symbols:
- `SessionProjectPersistenceMixin` (class): Mixin for project save and load payload persistence.

## `phage_annotator.session.project_recovery`

Project relink and recovery helpers.

Public documented symbols:
- `SessionProjectRecoveryMixin` (class): Mixin for project relink and recovery workflows.

## `phage_annotator.session.qc_state`

QC issue state management.

Public documented symbols:
- `QCState` (class): State for QC issues and validation.

## `phage_annotator.session.qc_thresholds`

QC thresholds and sensitivity configuration.

Public documented symbols:
- `QCThresholds` (class): Centralized QC parameter configuration.
- `get_default_thresholds` (function): Get or create default thresholds instance.
- `set_default_thresholds` (function): Set global default thresholds.

## `phage_annotator.session.session_annotation_iomixin_part1`

Extracted method group 1 for SessionAnnotationIOMixin.

Public documented symbols:
- `SessionAnnotationIOMixinPart1` (class): Method group 1 extracted from SessionAnnotationIOMixin.

## `phage_annotator.session.session_annotation_iomixin_part2`

Extracted method group 2 for SessionAnnotationIOMixin.

Public documented symbols:
- `SessionAnnotationIOMixinPart2` (class): Method group 2 extracted from SessionAnnotationIOMixin.

## `phage_annotator.session.session_controller_suggestions_mixin_part1`

Extracted method group 1 for SessionControllerSuggestionsMixin.

Public documented symbols:
- `SessionControllerSuggestionsMixinPart1` (class): Method group 1 extracted from SessionControllerSuggestionsMixin.

## `phage_annotator.session.session_controller_suggestions_mixin_part2`

Extracted method group 2 for SessionControllerSuggestionsMixin.

Public documented symbols:
- `SessionControllerSuggestionsMixinPart2` (class): Method group 2 extracted from SessionControllerSuggestionsMixin.

## `phage_annotator.session.session_controller_suggestions_mixin_part3`

Extracted method group 3 for SessionControllerSuggestionsMixin.

Public documented symbols:
- `SessionControllerSuggestionsMixinPart3` (class): Method group 3 extracted from SessionControllerSuggestionsMixin.

## `phage_annotator.session.session_controller_suggestions_mixin_part4`

Extracted method group 4 for SessionControllerSuggestionsMixin.

Public documented symbols:
- `SessionControllerSuggestionsMixinPart4` (class): Method group 4 extracted from SessionControllerSuggestionsMixin.

## `phage_annotator.session.session_controller_suggestions_mixin_part5`

Extracted method group 5 for SessionControllerSuggestionsMixin.

Public documented symbols:
- `SessionControllerSuggestionsMixinPart5` (class): Method group 5 extracted from SessionControllerSuggestionsMixin.

## `phage_annotator.session.session_controller_suggestions_mixin_part6`

Extracted method group 6 for SessionControllerSuggestionsMixin.

Public documented symbols:
- `SessionControllerSuggestionsMixinPart6` (class): Method group 6 extracted from SessionControllerSuggestionsMixin.

## `phage_annotator.session.session_project_bridge_mixin_part1`

Extracted method group 1 for SessionProjectBridgeMixin.

Public documented symbols:
- `SessionProjectBridgeMixinPart1` (class): Method group 1 extracted from SessionProjectBridgeMixin.

## `phage_annotator.session.session_project_bridge_mixin_part2`

Extracted method group 2 for SessionProjectBridgeMixin.

Public documented symbols:
- `SessionProjectBridgeMixinPart2` (class): Method group 2 extracted from SessionProjectBridgeMixin.

## `phage_annotator.session.signal_hub`

Centralized signal emit helpers for SessionController.

Public documented symbols:
- `ControllerSignals` (class): Canonical SessionController signal names.
- `emit_controller_signal` (function): Emit a Qt signal by canonical string name if available.
- `publish_event` (function): Publish an application event if the global event service is ready.
- `emit_state_changed` (function): Emit state changed for the current workflow.
- `annotation_notification_batch` (function): Coalesce repeated annotation notifications into one Qt emit plus per-image events.
- `emit_view_changed` (function): Emit view changed for the current workflow.
- `emit_display_changed` (function): Emit display changed for the current workflow.
- `emit_playback_changed` (function): Emit playback changed for the current workflow.
- `emit_roi_changed` (function): Emit roi changed for the current workflow.
- `emit_error` (function): Emit error for the current workflow.
- `emit_annotations_changed` (function): Emit centralized annotation-change updates to Qt + event bus.

## `phage_annotator.session.state`

Backward compatibility facade for session state models.

## `phage_annotator.session.suggestion_commands`

Undoable commands for assisted annotation suggestions.

## `phage_annotator.session.suggestion_commands_part1`

Extracted definitions group 1 for suggestion_commands.

Public documented symbols:
- `AcceptSuggestionCommand` (class): Accept a pending suggestion into committed annotations.

## `phage_annotator.session.suggestion_commands_part2`

Extracted definitions group 2 for suggestion_commands.

Public documented symbols:
- `RejectSuggestionCommand` (class): Reject and remove one pending suggestion.
- `ClearSuggestionsCommand` (class): Clear pending suggestions for one image.

## `phage_annotator.session.suggestion_commands_part3`

Extracted definitions group 3 for suggestion_commands.

Public documented symbols:
- `AcceptSuggestionsBatchCommand` (class): Accept multiple suggestions as a single undoable batch operation.

## `phage_annotator.session.view`

View and display state mutations for the session controller.

Public documented symbols:
- `SessionViewMixin` (class): Mixin for view and display state mutations (P3.1: extended for undo/redo).

## `phage_annotator.session.view_sync`

Zoom and pan synchronization for multi-modality views.

## `phage_annotator.session.view_sync_manager_part1`

Extracted method group 1 for ViewSyncManager.

Public documented symbols:
- `ViewSyncManagerPart1` (class): Method group 1 extracted from ViewSyncManager.

## `phage_annotator.session.view_sync_manager_part2`

Extracted method group 2 for ViewSyncManager.

Public documented symbols:
- `ViewSyncManagerPart2` (class): Method group 2 extracted from ViewSyncManager.

## `phage_annotator.session.view_sync_manager_part3`

Extracted method group 3 for ViewSyncManager.

Public documented symbols:
- `ViewSyncManagerPart3` (class): Method group 3 extracted from ViewSyncManager.

## `phage_annotator.session.view_sync_manager_part4`

Extracted method group 4 for ViewSyncManager.

Public documented symbols:
- `ViewSyncManagerPart4` (class): Method group 4 extracted from ViewSyncManager.

## `phage_annotator.session.view_sync_manager_part5`

Extracted method group 5 for ViewSyncManager.

Public documented symbols:
- `ViewSyncManagerPart5` (class): Method group 5 extracted from ViewSyncManager.

## `phage_annotator.session.view_sync_part1`

Extracted definitions group 1 for view_sync.

Public documented symbols:
- `ViewState` (class): View state for a single modality canvas.

## `phage_annotator.session.view_sync_part2`

Extracted definitions group 2 for view_sync.

Public documented symbols:
- `ViewSyncManager` (class): Manages zoom, pan, slice, and crop synchronization across multiple modalities.

## `phage_annotator.smlm`

SMLM (Single-Molecule Localization Microscopy) module (P3 refactoring).

## `phage_annotator.smlm.backends`

SMLM backend adapters (internal and Fiji/ThunderSTORM bridge modes).

## `phage_annotator.smlm.backends_part1`

Extracted definitions group 1 for backends.

## `phage_annotator.smlm.backends_part1_part1`

Extracted definitions group 1 for backends_part1.

Public documented symbols:
- `SmlmBridgeError` (class): Base class for SMLM bridge failures with remediation hints.
- `FijiNotFoundError` (class): Raised when Fiji executable/app path is missing.
- `PluginNotFoundError` (class): Raised when plugin id/JAR cannot be resolved.
- `MacroExecutionError` (class): Raised when macro execution fails.
- `OutputMissingError` (class): Raised when bridge execution does not produce required artifacts.
- `CSVSchemaMismatchError` (class): Raised when output CSV schema is incompatible with parser contract.
- `FijiTimeoutError` (class): Raised when Fiji execution exceeds configured timeout.
- `ImageJRuntime` (class): Singleton runtime for PyImageJ initialization within a session.
- `ThunderstormBridgeConfig` (class): Configuration for bridge execution through Fiji/ImageJ.
- `run_thunderstorm_backend` (function): Run SMLM using configured backend and return normalized outputs.

## `phage_annotator.smlm.backends_part1_part2`

Extracted definitions group 2 for backends_part1.

## `phage_annotator.smlm.backends_part1_part3`

Extracted definitions group 3 for backends_part1.

## `phage_annotator.smlm.backends_part2`

Extracted definitions group 2 for backends.

Public documented symbols:
- `discover_bundled_thunderstorm_jar` (function): Locate a bundled ThunderSTORM JAR in common project locations.

## `phage_annotator.smlm.demo_cli`

Smoke-test CLI for SMLM/Fiji bridge demo runs.

Public documented symbols:
- `main` (function): Run a tiny deterministic SMLM demo and export artifacts.

## `phage_annotator.smlm.external_plugins`

Discovery, manifest parsing, and execution helpers for external Fiji plugins.

## `phage_annotator.smlm.external_plugins_cli`

CLI utilities for external Fiji plugin manifest onboarding.

Public documented symbols:
- `main` (function): Fiji plugin adapter tooling.
- `list_commands` (function): List commands discovered from plugins.config inside a jar.
- `validate_manifest` (function): Validate strict manifest by discovery parsing.
- `scaffold_manifest` (function): Generate a starter strict manifest JSON from jar command discovery.

## `phage_annotator.smlm.external_plugins_part1`

Extracted definitions group 1 for external_plugins.

Public documented symbols:
- `ManifestParameter` (class): Typed plugin parameter specification.
- `PluginExecutionManifest` (class): Strict plugin execution contract.
- `ExternalFijiPlugin` (class): Descriptor for an external Fiji plugin artifact.
- `discover_external_fiji_plugins` (function): Discover plugin descriptors from `external_plugins` folder.
- `plugin_map` (function): Build map of plugin id -> descriptor.
- `resolve_plugin_jar` (function): Resolve effective plugin jar path from selection and overrides.
- `resolve_plugin_descriptor` (function): Resolve descriptor for selected plugin id.
- `build_plugin_arg_string` (function): Build Fiji argument string from strict manifest definition.
- `validate_plugin_parameters` (function): Validate/coerce typed plugin parameters.

## `phage_annotator.smlm.external_plugins_part2`

Extracted definitions group 2 for external_plugins.

Public documented symbols:
- `build_manifest_macro` (function): Generate macro text from plugin manifest run command + template.
- `parse_plugins_config_from_jar` (function): Parse legacy ImageJ `plugins.config` from jar, if present.

## `phage_annotator.smlm.parity`

Parity harness for comparing internal SMLM vs Fiji/ThunderSTORM outputs.

Public documented symbols:
- `SmlmParityMetrics` (class): Summary metrics for localization parity.
- `compute_parity_metrics` (function): Compute frame-aware nearest-neighbor parity between two localization sets.

## `phage_annotator.smlm.parity_cli`

CLI for SMLM parity checks between internal and ThunderSTORM outputs.

Public documented symbols:
- `main` (function): Compute parity metrics from two localization CSV files.

## `phage_annotator.smlm.preflight`

Preflight checks for Fiji bridge execution.

Public documented symbols:
- `PreflightItem` (class): Single preflight check result.
- `PreflightReport` (class): Aggregate preflight report.
- `run_preflight` (function): Run deterministic preflight checks for configured backend.
- `report_to_text` (function): Format preflight report as multiline text.

## `phage_annotator.smlm.preflight_cli`

CLI entry point for SMLM/Fiji bridge preflight.

Public documented symbols:
- `main` (function): Run preflight checks and exit non-zero on failure.

## `phage_annotator.smlm.presets`

Presets for SMLM workflows (ThunderSTORM + Deep-STORM).

Public documented symbols:
- `ThunderPreset` (class): Parameter preset for the ThunderSTORM-style pipeline.
- `DeepPreset` (class): Parameter preset for Deep-STORM inference.

## `phage_annotator.smlm.reproducibility`

Helpers for reproducibility runbook mode in SMLM workflows.

Public documented symbols:
- `ReproducibilityRunbookState` (class): State used to lock parameters and store provenance events.
- `utc_now_iso` (function): Return UTC timestamp in stable ISO format.
- `lock_profile` (function): Lock a method profile for reproducibility mode.
- `resolve_profile` (function): Resolve effective run profile with runbook locking semantics.
- `append_provenance_event` (function): Append immutable provenance event to state.
- `export_reproducibility_bundle` (function): Write reproducibility runbook bundle for audit/replay.

## `phage_annotator.smlm.smlm_dock_widget_part1`

Extracted method group 1 for SmlmDockWidget.

Public documented symbols:
- `SmlmDockWidgetPart1` (class): Method group 1 extracted from SmlmDockWidget.

## `phage_annotator.smlm.smlm_dock_widget_part2`

Extracted method group 2 for SmlmDockWidget.

Public documented symbols:
- `SmlmDockWidgetPart2` (class): Method group 2 extracted from SmlmDockWidget.

## `phage_annotator.smlm.smlm_dock_widget_part3`

Extracted method group 3 for SmlmDockWidget.

Public documented symbols:
- `SmlmDockWidgetPart3` (class): Method group 3 extracted from SmlmDockWidget.

## `phage_annotator.smlm.thunderstorm`

Backward compatibility facade. Moved to phage_annotator.algorithms.smlm_thunderstorm

## `phage_annotator.smlm.ui`

Backward compatibility facade for smlm_ui.

## `phage_annotator.smlm.widget`

Qt widget for ThunderSTORM-style SMLM controls.

## `phage_annotator.smlm.widget_part1`

Extracted definitions group 1 for widget.

Public documented symbols:
- `SmlmUiValues` (class): Snapshot of SMLM parameter values from the UI.

## `phage_annotator.smlm.widget_part2`

Extracted definitions group 2 for widget.

Public documented symbols:
- `SmlmDockWidget` (class): Parameter panel for the ThunderSTORM-style pipeline.

## `phage_annotator.tools`

Interactive tool routing utilities.

## `phage_annotator.tools.router`

Tool routing for interactive canvas behavior.

Public documented symbols:
- `Tool` (class): Interactive tool modes for the canvas.
- `ToolCallbacks` (class): Callback interface for ToolRouter to interact with the GUI.
- `ToolRouter` (class): Route Matplotlib mouse events to the active tool behavior.

## `phage_annotator.tools.utils`

Utility helpers for tools and system utilities.

## `phage_annotator.tools.utils.gpu_utils`

GPU availability checking utilities.

Public documented symbols:
- `check_cuda_available` (function): Check if CUDA/GPU is available for inference.
- `get_recommended_device` (function): Get recommended device for inference, with optional warning message.

## `phage_annotator.ui_qt`

Qt-based GUI application for microscopy image annotation (Layer 6).

## `phage_annotator.ui_qt.actions`

Menu and toolbar actions for the GUI application.

## `phage_annotator.ui_qt.actions.actions_mixin_part1`

Extracted method group 1 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart1` (class): Method group 1 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part10`

Extracted method group 10 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart10` (class): Method group 10 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part11`

Extracted method group 11 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart11` (class): Method group 11 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part12`

Extracted method group 12 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart12` (class): Method group 12 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part13`

Extracted method group 13 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart13` (class): Method group 13 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part14`

Extracted method group 14 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart14` (class): Method group 14 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part15`

Extracted method group 15 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart15` (class): Method group 15 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part16`

Extracted method group 16 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart16` (class): Method group 16 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part2`

Extracted method group 2 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart2` (class): Method group 2 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part3`

Extracted method group 3 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart3` (class): Method group 3 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part4`

Extracted method group 4 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart4` (class): Method group 4 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part5`

Extracted method group 5 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart5` (class): Method group 5 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part6`

Extracted method group 6 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart6` (class): Method group 6 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part7`

Extracted method group 7 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart7` (class): Method group 7 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part8`

Extracted method group 8 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart8` (class): Method group 8 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.actions_mixin_part9`

Extracted method group 9 for ActionsMixin.

Public documented symbols:
- `ActionsMixinPart9` (class): Method group 9 extracted from ActionsMixin.

## `phage_annotator.ui_qt.actions.assist_context`

Assist-context helpers extracted from the main actions mixin.

Public documented symbols:
- `AssistContextMixin` (class): Mixin for suggestion freshness and assist-context tracking.

## `phage_annotator.ui_qt.actions.assist_generation`

Assist generation and batch suggestion workflow helpers.

## `phage_annotator.ui_qt.actions.assist_generation_part1`

Extracted definitions group 1 for assist_generation.

Public documented symbols:
- `suggest_points_current_slice` (function): Generate ranked suggestions for the active T/Z slice.
- `suggest_points_current_image` (function): Generate ranked suggestions for every T/Z slice in the current image.

## `phage_annotator.ui_qt.actions.assist_generation_part2`

Extracted definitions group 2 for assist_generation.

Public documented symbols:
- `preview_batch_accept_dialog` (function): Show the suggestion preflight dialog and return accepted IDs.
- `accept_visible_suggestions` (function): Accept visible suggestions as one undoable batch.
- `accept_high_confidence_suggestions` (function): Accept visible high-confidence suggestions.
- `reject_visible_suggestions` (function): Reject all visible suggestions.

## `phage_annotator.ui_qt.actions.assist_generation_part3`

Extracted definitions group 3 for assist_generation.

Public documented symbols:
- `accept_suggestions_in_roi` (function): Accept the currently visible suggestions inside the active ROI.
- `clear_suggestions_current_image` (function): Clear pending suggestions for the current image.

## `phage_annotator.ui_qt.actions.assist_review`

Assist review queue and suggestion-decision helpers.

## `phage_annotator.ui_qt.actions.assist_review_part1`

Extracted definitions group 1 for assist_review.

Public documented symbols:
- `review_throughput_snapshot` (function): Return compact throughput text and avg seconds per decision.
- `calibration_sparkline_text` (function): Return a small calibration sparkline from accepted/rejected history.
- `review_queue_progress_counts` (function): Return processed/total counts for the current review scope.
- `refresh_review_queue_panel` (function): Refresh the review queue UI without keeping the logic in standard.py.

## `phage_annotator.ui_qt.actions.assist_review_part2`

Extracted definitions group 2 for assist_review.

Public documented symbols:
- `on_review_queue_row_selected` (function): Handle row selection from the review queue table.
- `confirm_suggestion_redecision` (function): Confirm destructive accepted->non-accepted transitions.
- `set_selected_suggestion_decision` (function): Change suggestion decision through the controller/command layer.

## `phage_annotator.ui_qt.actions.assist_strategy`

Suggestion-strategy UI helpers extracted from the main actions mixin.

Public documented symbols:
- `AssistStrategyMixin` (class): Mixin for suggestion-strategy selection and status-bar synchronization.

## `phage_annotator.ui_qt.actions.assist_training`

Assist ranker training and calibration helpers.

Public documented symbols:
- `on_suggestion_auto_retrain_changed` (function): Persist auto-retrain enablement through the controller boundary.
- `on_suggestion_min_labels_changed` (function): Persist the minimum labels threshold for auto-retraining.
- `train_suggestion_ranker_now` (function): Force immediate suggestion-ranker training.
- `show_calibration_visualizer` (function): Display the acceptance-likelihood calibration plot.

## `phage_annotator.ui_qt.actions.dock_actions`

Dock and panel visibility actions.

Public documented symbols:
- `DockActionsMixin` (class): Panel visibility actions with synchronized dock/menu/button state.

## `phage_annotator.ui_qt.actions.events`

Event wiring and interaction handlers.

Public documented symbols:
- `EventsMixin` (class): Mixin for Qt/matplotlib event handlers and interaction state.

## `phage_annotator.ui_qt.actions.events_mixin_part1`

Extracted method group 1 for EventsMixin.

Public documented symbols:
- `EventsMixinPart1` (class): Method group 1 extracted from EventsMixin.

## `phage_annotator.ui_qt.actions.events_mixin_part2`

Extracted method group 2 for EventsMixin.

Public documented symbols:
- `EventsMixinPart2` (class): Method group 2 extracted from EventsMixin.

## `phage_annotator.ui_qt.actions.events_mixin_part3`

Extracted method group 3 for EventsMixin.

Public documented symbols:
- `EventsMixinPart3` (class): Method group 3 extracted from EventsMixin.

## `phage_annotator.ui_qt.actions.export_actions`

Export and reviewer analytics actions.

Public documented symbols:
- `ExportActionsMixin` (class): Standard-export and reviewer analytics dialogs.

## `phage_annotator.ui_qt.actions.file`

File and folder loading actions (extracted from gui_actions.py).

Public documented symbols:
- `FileActionsMixin` (class): Mixin for file and folder loading operations.

## `phage_annotator.ui_qt.actions.keyboard_events`

Keyboard dispatch mixin.

Public documented symbols:
- `KeyboardEventsMixin` (class): Qt and Matplotlib keyboard shortcut handlers.

## `phage_annotator.ui_qt.actions.navigation_actions`

Navigation-related actions.

Public documented symbols:
- `NavigationActionsMixin` (class): Frame/Z navigation dialogs and command execution.

## `phage_annotator.ui_qt.actions.qc_actions`

QC workflow actions.

Public documented symbols:
- `QCActionsMixin` (class): Quality-control issue validation, navigation, and export actions.

## `phage_annotator.ui_qt.actions.qcactions_mixin_part1`

Extracted method group 1 for QCActionsMixin.

Public documented symbols:
- `QCActionsMixinPart1` (class): Method group 1 extracted from QCActionsMixin.

## `phage_annotator.ui_qt.actions.qcactions_mixin_part2`

Extracted method group 2 for QCActionsMixin.

Public documented symbols:
- `QCActionsMixinPart2` (class): Method group 2 extracted from QCActionsMixin.

## `phage_annotator.ui_qt.actions.standard`

Menu and dialog actions for the GUI.

Public documented symbols:
- `ActionsMixin` (class): Mixin for File/View/Analyze actions and dialogs.

## `phage_annotator.ui_qt.actions.standard_workspace`

Workspace, recent-file, and annotation-load actions.

Public documented symbols:
- `WorkspaceActionsMixin` (class): Mixin for workspace I/O, recent files, and metadata dock updates.

## `phage_annotator.ui_qt.actions.workspace_actions_mixin_part1`

Extracted method group 1 for WorkspaceActionsMixin.

Public documented symbols:
- `WorkspaceActionsMixinPart1` (class): Method group 1 extracted from WorkspaceActionsMixin.

## `phage_annotator.ui_qt.actions.workspace_actions_mixin_part2`

Extracted method group 2 for WorkspaceActionsMixin.

Public documented symbols:
- `WorkspaceActionsMixinPart2` (class): Method group 2 extracted from WorkspaceActionsMixin.

## `phage_annotator.ui_qt.actions.workspace_actions_mixin_part3`

Extracted method group 3 for WorkspaceActionsMixin.

Public documented symbols:
- `WorkspaceActionsMixinPart3` (class): Method group 3 extracted from WorkspaceActionsMixin.

## `phage_annotator.ui_qt.assist_state`

Canonical assist-state definitions and presentation helpers.

Public documented symbols:
- `AssistState` (class): Canonical assisted-annotation trust states.
- `AssistStatePresentation` (class): Display metadata for assist-state widgets/tooltips.
- `assist_state_label` (function): Return the canonical label for an assist state.
- `assist_state_color` (function): Return the canonical color for an assist state.
- `infer_assist_state` (function): Infer canonical assist-state from controller status and suggestion metadata.

## `phage_annotator.ui_qt.controls`

Qt-based control widgets.

## `phage_annotator.ui_qt.controls.base`

Aggregate control mixins for UI handlers.

Public documented symbols:
- `ControlsMixin` (class): Mixin for GUI control handlers.

## `phage_annotator.ui_qt.controls.density`

Density model inference controls.

Public documented symbols:
- `DensityControlsMixin` (class): Mixin for density model inference controls.

## `phage_annotator.ui_qt.controls.display`

Display, playback, and general control handlers.

Public documented symbols:
- `DisplayControlsMixin` (class): Mixin for display, playback, and general control handlers.

## `phage_annotator.ui_qt.controls.display_contrast`

Brightness/contrast and display-setting helpers.

Public documented symbols:
- `DisplayContrastMixin` (class): Mixin for brightness/contrast and display-setting controls.

## `phage_annotator.ui_qt.controls.display_contrast_mixin_part1`

Extracted method group 1 for DisplayContrastMixin.

Public documented symbols:
- `DisplayContrastMixinPart1` (class): Method group 1 extracted from DisplayContrastMixin.

## `phage_annotator.ui_qt.controls.display_contrast_mixin_part2`

Extracted method group 2 for DisplayContrastMixin.

Public documented symbols:
- `DisplayContrastMixinPart2` (class): Method group 2 extracted from DisplayContrastMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part1`

Extracted method group 1 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart1` (class): Method group 1 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part2`

Extracted method group 2 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart2` (class): Method group 2 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part3`

Extracted method group 3 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart3` (class): Method group 3 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part4`

Extracted method group 4 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart4` (class): Method group 4 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part5`

Extracted method group 5 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart5` (class): Method group 5 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part6`

Extracted method group 6 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart6` (class): Method group 6 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part7`

Extracted method group 7 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart7` (class): Method group 7 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part8`

Extracted method group 8 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart8` (class): Method group 8 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.display_controls_mixin_part9`

Extracted method group 9 for DisplayControlsMixin.

Public documented symbols:
- `DisplayControlsMixinPart9` (class): Method group 9 extracted from DisplayControlsMixin.

## `phage_annotator.ui_qt.controls.preferences`

Preferences and configuration handlers.

Public documented symbols:
- `PreferencesControlsMixin` (class): Mixin for preferences and configuration handlers.

## `phage_annotator.ui_qt.controls.preferences_controls_mixin_part1`

Extracted method group 1 for PreferencesControlsMixin.

Public documented symbols:
- `PreferencesControlsMixinPart1` (class): Method group 1 extracted from PreferencesControlsMixin.

## `phage_annotator.ui_qt.controls.preferences_controls_mixin_part2`

Extracted method group 2 for PreferencesControlsMixin.

Public documented symbols:
- `PreferencesControlsMixinPart2` (class): Method group 2 extracted from PreferencesControlsMixin.

## `phage_annotator.ui_qt.controls.recorder`

Action recorder handlers.

Public documented symbols:
- `RecorderControlsMixin` (class): Mixin for action recorder handlers.

## `phage_annotator.ui_qt.controls.results`

Results table handlers.

Public documented symbols:
- `ResultsControlsMixin` (class): Mixin for results table handlers.

## `phage_annotator.ui_qt.controls.roi`

ROI manager and ROI measurement handlers with Fiji-parity support.

Public documented symbols:
- `RoiControlsMixin` (class): Mixin for ROI manager and ROI measurement handlers.

## `phage_annotator.ui_qt.controls.roi_controls_mixin_part1`

Extracted method group 1 for RoiControlsMixin.

Public documented symbols:
- `RoiControlsMixinPart1` (class): Method group 1 extracted from RoiControlsMixin.

## `phage_annotator.ui_qt.controls.roi_controls_mixin_part2`

Extracted method group 2 for RoiControlsMixin.

Public documented symbols:
- `RoiControlsMixinPart2` (class): Method group 2 extracted from RoiControlsMixin.

## `phage_annotator.ui_qt.controls.roi_controls_mixin_part3`

Extracted method group 3 for RoiControlsMixin.

Public documented symbols:
- `RoiControlsMixinPart3` (class): Method group 3 extracted from RoiControlsMixin.

## `phage_annotator.ui_qt.controls.roi_controls_mixin_part4`

Extracted method group 4 for RoiControlsMixin.

Public documented symbols:
- `RoiControlsMixinPart4` (class): Method group 4 extracted from RoiControlsMixin.

## `phage_annotator.ui_qt.controls.roi_controls_mixin_part5`

Extracted method group 5 for RoiControlsMixin.

Public documented symbols:
- `RoiControlsMixinPart5` (class): Method group 5 extracted from RoiControlsMixin.

## `phage_annotator.ui_qt.controls.smlm`

SMLM (ThunderSTORM/Deep-STORM) handlers.

Public documented symbols:
- `SmlmControlsMixin` (class): Mixin for SMLM (ThunderSTORM/Deep-STORM) handlers.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part1`

Extracted method group 1 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart1` (class): Method group 1 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part2`

Extracted method group 2 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart2` (class): Method group 2 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part3`

Extracted method group 3 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart3` (class): Method group 3 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part4`

Extracted method group 4 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart4` (class): Method group 4 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part5`

Extracted method group 5 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart5` (class): Method group 5 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part6`

Extracted method group 6 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart6` (class): Method group 6 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.smlm_controls_mixin_part7`

Extracted method group 7 for SmlmControlsMixin.

Public documented symbols:
- `SmlmControlsMixinPart7` (class): Method group 7 extracted from SmlmControlsMixin.

## `phage_annotator.ui_qt.controls.threshold`

Thresholding and particle analysis handlers.

Public documented symbols:
- `ThresholdControlsMixin` (class): Mixin for thresholding and particle analysis handlers.

## `phage_annotator.ui_qt.controls.threshold_controls_mixin_part1`

Extracted method group 1 for ThresholdControlsMixin.

Public documented symbols:
- `ThresholdControlsMixinPart1` (class): Method group 1 extracted from ThresholdControlsMixin.

## `phage_annotator.ui_qt.controls.threshold_controls_mixin_part2`

Extracted method group 2 for ThresholdControlsMixin.

Public documented symbols:
- `ThresholdControlsMixinPart2` (class): Method group 2 extracted from ThresholdControlsMixin.

## `phage_annotator.ui_qt.controls.threshold_controls_mixin_part3`

Extracted method group 3 for ThresholdControlsMixin.

Public documented symbols:
- `ThresholdControlsMixinPart3` (class): Method group 3 extracted from ThresholdControlsMixin.

## `phage_annotator.ui_qt.controls.threshold_controls_mixin_part4`

Extracted method group 4 for ThresholdControlsMixin.

Public documented symbols:
- `ThresholdControlsMixinPart4` (class): Method group 4 extracted from ThresholdControlsMixin.

## `phage_annotator.ui_qt.dialogs`

Qt dialogs for phage annotator.

## `phage_annotator.ui_qt.dialogs.bulk_metadata_editor_dialog`

Bulk metadata editor for multiple annotations.

Public documented symbols:
- `BulkMetadataEditorDialog` (class): Dialog for batch editing metadata on multiple annotations.

## `phage_annotator.ui_qt.dialogs.contrast_adjustment_dialog`

Contrast adjustment dialog with professional brightness controls.

Public documented symbols:
- `ContrastAdjustmentDialog` (class): Professional contrast adjustment dialog.

## `phage_annotator.ui_qt.dialogs.metadata_editor_dialog`

Metadata editor dialog for single annotation.

Public documented symbols:
- `MetadataEditorDialog` (class): Dialog for editing annotation metadata.

## `phage_annotator.ui_qt.dialogs.modality_rename_dialog`

Modality renaming dialog for user-customizable modality names.

Public documented symbols:
- `ModalityRenamingDialog` (class): Dialog for renaming a modality with validation.

## `phage_annotator.ui_qt.dialogs.rename_modality_dialog`

Dialog for renaming a modality with validation.

Public documented symbols:
- `RenameModalityDialog` (class): Dialog for renaming a modality with validation.
- `show_rename_modality_dialog` (function): Convenience function to show rename dialog and return result.

## `phage_annotator.ui_qt.docks`

Qt dock widget exports.

## `phage_annotator.ui_qt.docks.metadata_dock`

Metadata viewer dock for raw and parsed image metadata.

Public documented symbols:
- `MetadataDock` (class): Viewer widget for TIFF/OME metadata with search and raw view.

## `phage_annotator.ui_qt.handlers.keyboard_handlers`

Keyboard shortcuts and actions handlers for B&C system integration.

Public documented symbols:
- `KeyboardHandlersMixin` (class): Mixin providing keyboard shortcut callback methods.

## `phage_annotator.ui_qt.integration`

Integration modules for GUI component wiring.

## `phage_annotator.ui_qt.integration.channel_integration`

Integration module for wiring channel controls to session state.

Public documented symbols:
- `ChannelPanelIntegration` (class): Integrator for channel panel with session state.

## `phage_annotator.ui_qt.keyboard_registry`

Central keyboard shortcut registry.

Public documented symbols:
- `ShortcutEntry` (class): Shortcut definition used by handlers, dialogs, and menu actions.
- `all_shortcuts` (function): Run the all shortcuts workflow.
- `detect_conflicts` (function): Return duplicate (context, shortcut) conflicts.
- `dialog_rows` (function): Rows for KeyboardShortcutsDialog table.
- `apply_menu_shortcuts` (function): Apply registered shortcuts to menu/toolbar Qt actions when available.
- `qt_match` (function): Run the qt match workflow.
- `matplotlib_key_bindings` (function): Map Matplotlib key string -> action id.
- `qt_key_bindings` (function): Map Qt key/modifier pairs -> action id.

## `phage_annotator.ui_qt.keyboard_shortcut_manager_part1`

Extracted method group 1 for KeyboardShortcutManager.

Public documented symbols:
- `KeyboardShortcutManagerPart1` (class): Method group 1 extracted from KeyboardShortcutManager.

## `phage_annotator.ui_qt.keyboard_shortcut_manager_part2`

Extracted method group 2 for KeyboardShortcutManager.

Public documented symbols:
- `KeyboardShortcutManagerPart2` (class): Method group 2 extracted from KeyboardShortcutManager.

## `phage_annotator.ui_qt.keyboard_shortcut_manager_part3`

Extracted method group 3 for KeyboardShortcutManager.

Public documented symbols:
- `KeyboardShortcutManagerPart3` (class): Method group 3 extracted from KeyboardShortcutManager.

## `phage_annotator.ui_qt.keyboard_shortcuts`

Keyboard shortcut management and conflict detection.

## `phage_annotator.ui_qt.keyboard_shortcuts_part1`

Extracted definitions group 1 for keyboard_shortcuts.

Public documented symbols:
- `ShortcutContext` (class): Context where a shortcut can be active.
- `ShortcutDefinition` (class): Definition of a single keyboard shortcut.
- `ShortcutConflict` (class): Report of a shortcut conflict between two shortcuts.

## `phage_annotator.ui_qt.keyboard_shortcuts_part2`

Extracted definitions group 2 for keyboard_shortcuts.

Public documented symbols:
- `KeyboardShortcutManager` (class): Centralized keyboard shortcut management with conflict detection.

## `phage_annotator.ui_qt.main_window`

Matplotlib + Qt keypoint annotation GUI for microscopy TIFF stacks.

Public documented symbols:
- `KeypointAnnotator` (class): Main GUI window for keypoint annotation on T/Z image stacks.
- `create_app` (function): Create the Qt application and main window without starting the event loop.
- `run_gui` (function): Run gui for the current workflow.

## `phage_annotator.ui_qt.models`

Qt model package.

## `phage_annotator.ui_qt.models.lazy_loader`

State helpers for the lazy loader panel.

## `phage_annotator.ui_qt.models.lazy_loader_part1`

Extracted definitions group 1 for lazy_loader.

Public documented symbols:
- `LazyLoaderEntry` (class): Immutable tree entry shown in the lazy loader browser.
- `iter_tiff_paths` (function): Return TIFF files contained in ``root``.
- `LazyLoaderManifest` (class): Tree model for the lazy loader browser with one-step removal undo.

## `phage_annotator.ui_qt.models.lazy_loader_part2`

Extracted definitions group 2 for lazy_loader.

Public documented symbols:
- `LazyTableRowSpec` (class): Derived lazy-table row rendered from controller/view state.
- `normalize_lazy_sync_groups` (function): Return normalized numeric sync groups for the current lazy-table rows.

## `phage_annotator.ui_qt.panels`

Feature panels for the GUI application.

## `phage_annotator.ui_qt.panels.advanced_settings_panel`

Compact right-dock panel for infrequent expert settings.

Public documented symbols:
- `AdvancedSettingsPanel` (class): Right-side expert settings for calibration and infrequent controls.

## `phage_annotator.ui_qt.panels.analyze_particles_panel`

Backward compatibility facade for analyze_particles_panel.

## `phage_annotator.ui_qt.panels.channel_controls`

Channel control panel for multi-channel display management.

Public documented symbols:
- `ChannelControlPanel` (class): Panel widget for per-channel display control.

## `phage_annotator.ui_qt.panels.deepstorm`

Qt widget for Deep-STORM inference controls.

Public documented symbols:
- `DeepStormUiValues` (class): Snapshot of Deep-STORM parameter values from the UI.
- `DeepStormDockWidget` (class): Parameter panel for Deep-STORM inference.

## `phage_annotator.ui_qt.panels.density`

Density prediction panel widgets.

Public documented symbols:
- `DensityPanel` (class): Dock widget for density model inference controls.

## `phage_annotator.ui_qt.panels.density_panel`

Backward compatibility facade for density_panel.

## `phage_annotator.ui_qt.panels.particles`

Qt panel for Analyze Particles controls.

Public documented symbols:
- `AnalyzeParticlesValues` (class): Snapshot of Analyze Particles controls.
- `AnalyzeParticlesPanel` (class): Analyze Particles panel with filters and results table.

## `phage_annotator.ui_qt.panels.performance`

Consolidated performance monitoring panel for cache, jobs, and buffers.

Public documented symbols:
- `PerformancePanel` (class): Real-time performance metrics panel for cache, jobs, and buffers.

## `phage_annotator.ui_qt.panels.performance_panel`

Backward compatibility facade for performance_panel.

## `phage_annotator.ui_qt.panels.performance_panel_part1`

Extracted method group 1 for PerformancePanel.

Public documented symbols:
- `PerformancePanelPart1` (class): Method group 1 extracted from PerformancePanel.

## `phage_annotator.ui_qt.panels.performance_panel_part2`

Extracted method group 2 for PerformancePanel.

Public documented symbols:
- `PerformancePanelPart2` (class): Method group 2 extracted from PerformancePanel.

## `phage_annotator.ui_qt.panels.performance_panel_part3`

Extracted method group 3 for PerformancePanel.

Public documented symbols:
- `PerformancePanelPart3` (class): Method group 3 extracted from PerformancePanel.

## `phage_annotator.ui_qt.panels.qc_issues_panel`

QC issues panel for quality-control and problem review workflows.

Public documented symbols:
- `QCIssuesPanel` (class): Dock widget panel displaying QC issues with filtering and navigation.

## `phage_annotator.ui_qt.panels.qc_thresholds_panel`

QC Thresholds settings panel for interactive tuning.

## `phage_annotator.ui_qt.panels.qc_thresholds_panel_part1`

Extracted definitions group 1 for qc_thresholds_panel.

Public documented symbols:
- `QCThresholdsPanel` (class): Dialog for configuring QC thresholds.

## `phage_annotator.ui_qt.panels.qc_thresholds_panel_part2`

Extracted definitions group 2 for qc_thresholds_panel.

Public documented symbols:
- `show_qc_thresholds_dialog` (function): Show QC thresholds dialog and return configured thresholds.

## `phage_annotator.ui_qt.panels.qcissues_panel_part1`

Extracted method group 1 for QCIssuesPanel.

Public documented symbols:
- `QCIssuesPanelPart1` (class): Method group 1 extracted from QCIssuesPanel.

## `phage_annotator.ui_qt.panels.qcissues_panel_part2`

Extracted method group 2 for QCIssuesPanel.

Public documented symbols:
- `QCIssuesPanelPart2` (class): Method group 2 extracted from QCIssuesPanel.

## `phage_annotator.ui_qt.panels.qcthresholds_panel_part1`

Extracted method group 1 for QCThresholdsPanel.

Public documented symbols:
- `QCThresholdsPanelPart1` (class): Method group 1 extracted from QCThresholdsPanel.

## `phage_annotator.ui_qt.panels.qcthresholds_panel_part2`

Extracted method group 2 for QCThresholdsPanel.

Public documented symbols:
- `QCThresholdsPanelPart2` (class): Method group 2 extracted from QCThresholdsPanel.

## `phage_annotator.ui_qt.panels.qcthresholds_panel_part3`

Extracted method group 3 for QCThresholdsPanel.

Public documented symbols:
- `QCThresholdsPanelPart3` (class): Method group 3 extracted from QCThresholdsPanel.

## `phage_annotator.ui_qt.panels.recorder`

Lightweight action recorder for GUI events.

Public documented symbols:
- `ActionRecorder` (class): Append-only action recorder with simple text serialization.
- `RecorderWidget` (class): Recorder dock widget with copy/save controls.

## `phage_annotator.ui_qt.panels.registry`

Panel registry specs for dock creation.

Public documented symbols:
- `PanelConstraints` (class): Behavior constraints for panel placement and floating.
- `PanelSpec` (class): Declarative spec for a dockable panel.
- `roi_manager_spec` (function): Helper to build ROI Manager panel spec.

## `phage_annotator.ui_qt.panels.registry_impl`

Backward compatibility facade for panel registry.

## `phage_annotator.ui_qt.panels.review_queue_panel`

Review queue panel for assisted-annotation triage workflows.

Public documented symbols:
- `ReviewQueuePanel` (class): Right-dock panel showing current uncertain suggestion and queue progress.

## `phage_annotator.ui_qt.panels.review_queue_panel_part1`

Extracted method group 1 for ReviewQueuePanel.

Public documented symbols:
- `ReviewQueuePanelPart1` (class): Method group 1 extracted from ReviewQueuePanel.

## `phage_annotator.ui_qt.panels.review_queue_panel_part2`

Extracted method group 2 for ReviewQueuePanel.

Public documented symbols:
- `ReviewQueuePanelPart2` (class): Method group 2 extracted from ReviewQueuePanel.

## `phage_annotator.ui_qt.panels.smlm`

Unified SMLM UI panel with presets for ThunderSTORM and Deep-STORM.

Public documented symbols:
- `SmlmPanel` (class): Unified SMLM panel with presets and per-method tabs.

## `phage_annotator.ui_qt.panels.status_details_panel`

Right-dock status details panel for overflow operational context.

Public documented symbols:
- `StatusDetailsPanel` (class): Compact, structured status details that don't fit in the bottom status bar.

## `phage_annotator.ui_qt.panels.suggestion_explain_panel`

Explainability panel for assisted suggestion trust cues.

Public documented symbols:
- `SuggestionExplainPanel` (class): Panel showing why the current suggestion was proposed.

## `phage_annotator.ui_qt.panels.threshold`

Qt panel for thresholding controls.

Public documented symbols:
- `ThresholdUiValues` (class): Snapshot of thresholding controls.
- `ThresholdPanel` (class): Threshold control panel with preview and post-processing.

## `phage_annotator.ui_qt.panels.threshold_panel`

Backward compatibility facade for threshold_panel.

## `phage_annotator.ui_qt.registry`

UI registries for panels, widgets, and actions.

## `phage_annotator.ui_qt.registry.panel_registry`

Panel registry for 10-panel maximum separation UI architecture.

Public documented symbols:
- `SidebarPanelSpec` (class): Declarative spec for a sidebar panel in the 10-panel architecture.
- `build_sidebar_panel_registry` (function): Build the registry of 10 sidebar panels.

## `phage_annotator.ui_qt.rendering`

Image rendering and visualization components.

## `phage_annotator.ui_qt.rendering.blend_kernels`

Numeric blend kernels used by channel compositing.

Public documented symbols:
- `blend_normal` (function): Composite ``layer`` over ``base`` with standard opacity blending.
- `blend_overlay` (function): Blend with overlay math that multiplies shadows and screens highlights.
- `blend_screen` (function): Blend with screen math so brighter pixels dominate the composition.
- `blend_multiply` (function): Blend with multiply math so darker pixels dominate the composition.
- `blend_add` (function): Add channel values directly without clipping the result.
- `blend_subtract` (function): Subtract channel values directly without clipping the result.

## `phage_annotator.ui_qt.rendering.blend_modes`

Blend mode implementations for multi-channel compositing.

Public documented symbols:
- `BlendMode` (class): Blend modes for channel compositing.
- `composite_channels` (function): Composite multiple channels with specified blend mode.
- `apply_per_channel_opacity` (function): Apply per-channel opacity values.

## `phage_annotator.ui_qt.rendering.export_view`

Export current view with overlays as PNG/TIFF.

## `phage_annotator.ui_qt.rendering.export_view_part1`

Extracted definitions group 1 for export_view.

## `phage_annotator.ui_qt.rendering.export_view_part1_part1`

Extracted definitions group 1 for export_view_part1.

Public documented symbols:
- `ExportValidationResult` (class): P4.2: Validation result for export preflight checks.
- `validate_export_preflight` (function): P4.2: Validate export options before execution.

## `phage_annotator.ui_qt.rendering.export_view_part1_part2`

Extracted definitions group 2 for export_view_part1.

Public documented symbols:
- `render_view_to_array` (function): Render a view with overlays into an RGBA array.

## `phage_annotator.ui_qt.rendering.export_view_part1_part3`

Extracted definitions group 3 for export_view_part1.

Public documented symbols:
- `render_layer_to_array` (function): Render a single layer (base, annotations, ROI, particles, or scalebar) with transparency.

## `phage_annotator.ui_qt.rendering.export_view_part1_part4`

Extracted definitions group 4 for export_view_part1.

Public documented symbols:
- `render_chunk_to_array` (function): Render a spatial chunk of the image with overlays (P4a: Streaming Export).

## `phage_annotator.ui_qt.rendering.export_view_part2`

Extracted definitions group 2 for export_view.

Public documented symbols:
- `StreamingExportWriter` (class): Base class for streaming export writers (P4a).
- `TiffStreamWriter` (class): TIFF-specific streaming export writer (P4a).
- `PngStreamWriter` (class): PNG-specific streaming export writer (P4a).
- `create_streaming_writer` (function): Create a streaming export writer for specified format (P4a).

## `phage_annotator.ui_qt.rendering.export_view_part3`

Extracted definitions group 3 for export_view.

Public documented symbols:
- `calculate_export_chunks` (function): Calculate chunk boundaries for streaming export (P4a).

## `phage_annotator.ui_qt.rendering.lut_manager`

LUT registry for display mapping.

Public documented symbols:
- `LutSpec` (class): LUT specification for a matplotlib colormap.
- `lut_names` (function): Return display names for all LUTs.
- `cmap_for` (function): Return a matplotlib colormap for the LUT spec.

## `phage_annotator.ui_qt.rendering.renderer`

Rendering pipeline helpers for the GUI.

Public documented symbols:
- `RenderingMixin` (class): Mixin for image rendering and overlay composition.

## `phage_annotator.ui_qt.rendering.renderer_overlays`

Overlay and header-building helpers for rendering.

Public documented symbols:
- `RenderingOverlayMixin` (class): Mixin for overlay, label, and header text generation.

## `phage_annotator.ui_qt.rendering.rendering_mixin_part1`

Extracted method group 1 for RenderingMixin.

Public documented symbols:
- `RenderingMixinPart1` (class): Method group 1 extracted from RenderingMixin.

## `phage_annotator.ui_qt.rendering.rendering_mixin_part2`

Extracted method group 2 for RenderingMixin.

Public documented symbols:
- `RenderingMixinPart2` (class): Method group 2 extracted from RenderingMixin.

## `phage_annotator.ui_qt.rendering.rendering_mixin_part3`

Extracted method group 3 for RenderingMixin.

Public documented symbols:
- `RenderingMixinPart3` (class): Method group 3 extracted from RenderingMixin.

## `phage_annotator.ui_qt.rendering.rendering_mixin_part4`

Extracted method group 4 for RenderingMixin.

Public documented symbols:
- `RenderingMixinPart4` (class): Method group 4 extracted from RenderingMixin.

## `phage_annotator.ui_qt.rendering.roi_crop`

ROI and crop helpers.

Public documented symbols:
- `RoiCropMixin` (class): Mixin for ROI and crop computations.

## `phage_annotator.ui_qt.rendering.roi_crop_mixin_part1`

Extracted method group 1 for RoiCropMixin.

Public documented symbols:
- `RoiCropMixinPart1` (class): Method group 1 extracted from RoiCropMixin.

## `phage_annotator.ui_qt.rendering.roi_crop_mixin_part2`

Extracted method group 2 for RoiCropMixin.

Public documented symbols:
- `RoiCropMixinPart2` (class): Method group 2 extracted from RoiCropMixin.

## `phage_annotator.ui_qt.rendering.roi_crop_mixin_part3`

Extracted method group 3 for RoiCropMixin.

Public documented symbols:
- `RoiCropMixinPart3` (class): Method group 3 extracted from RoiCropMixin.

## `phage_annotator.ui_qt.rendering.roi_crop_mixin_part4`

Extracted method group 4 for RoiCropMixin.

Public documented symbols:
- `RoiCropMixinPart4` (class): Method group 4 extracted from RoiCropMixin.

## `phage_annotator.ui_qt.runtime`

Runtime helpers for main-window initialization and services.

## `phage_annotator.ui_qt.runtime.window_runtime`

Runtime bootstrap helpers for the main Qt window.

## `phage_annotator.ui_qt.runtime.window_runtime_part1`

Extracted definitions group 1 for window_runtime.

Public documented symbols:
- `configure_window_behavior` (function): Apply non-modal window flags so the GUI stays cooperative with other apps.

## `phage_annotator.ui_qt.runtime.window_runtime_part2`

Extracted definitions group 2 for window_runtime.

## `phage_annotator.ui_qt.runtime.window_runtime_part2_part1`

Extracted definitions group 1 for window_runtime_part2.

Public documented symbols:
- `init_settings_runtime` (function): Initialize unified settings access and migrate persisted UI defaults.
- `init_display_runtime_preferences` (function): Initialize persisted display/layout preferences consumed across mixins.
- `init_view_runtime_state` (function): Initialize lightweight runtime state used by view/layout coordination.
- `init_playback_runtime_state` (function): Initialize playback buffers and pacing state.
- `init_refresh_runtime_state` (function): Initialize queued refresh and debounce timers.
- `init_render_job_runtime_state` (function): Initialize caches, job manager, and render-related runtime state.

## `phage_annotator.ui_qt.runtime.window_runtime_part2_part2`

Extracted definitions group 2 for window_runtime_part2.

Public documented symbols:
- `init_widget_placeholder_state` (function): Initialize widget references populated later during UI setup.
- `init_feature_runtime_state` (function): Initialize feature-specific runtime state and persisted toggles.
- `init_runtime_state` (function): Initialize window runtime state in explicit phases.
- `init_controller_runtime` (function): Create controller-owned runtime collaborators and dependent services.

## `phage_annotator.ui_qt.runtime.window_runtime_part2_part3`

Extracted definitions group 3 for window_runtime_part2.

Public documented symbols:
- `bootstrap_runtime` (function): Initialize window-local runtime state before widgets are built.

## `phage_annotator.ui_qt.runtime.window_services`

Service binding and startup helpers for the main Qt window.

Public documented symbols:
- `bootstrap_ui` (function): Build widgets and then attach signal-driven runtime integrations.
- `wire_view_sync_runtime` (function): Attach linked-view runtime handlers after widgets exist.
- `restore_runtime_action_state` (function): Restore widget-backed runtime toggles after UI setup.
- `bind_runtime_services` (function): Bind queued signals, recorder hooks, and global exception handling.
- `initialize_session_view` (function): Load initial images and establish the first synchronized viewport.
- `start_background_runtime` (function): Start low-priority background services after the first UI frame is queued.
- `finalize_runtime_startup` (function): Complete GUI startup after UI setup and signal binding.

## `phage_annotator.ui_qt.services`

Qt-specific service implementations and bridges.

## `phage_annotator.ui_qt.services.action_logger`

Unified UI action logging for both file storage and real-time GUI display.

Public documented symbols:
- `ActionLogger` (class): Unified action logger - handles BOTH file and GUI logging.
- `get_action_logger` (function): Get or create the global action logger instance.
- `init_action_logger` (function): Initialize the global action logger.

## `phage_annotator.ui_qt.services.job_manager_part1`

Extracted method group 1 for JobManager.

Public documented symbols:
- `JobManagerPart1` (class): Method group 1 extracted from JobManager.

## `phage_annotator.ui_qt.services.job_manager_part2`

Extracted method group 2 for JobManager.

Public documented symbols:
- `JobManagerPart2` (class): Method group 2 extracted from JobManager.

## `phage_annotator.ui_qt.services.job_manager_part3`

Extracted method group 3 for JobManager.

Public documented symbols:
- `JobManagerPart3` (class): Method group 3 extracted from JobManager.

## `phage_annotator.ui_qt.services.jobs`

Background job helpers using Qt thread pool.

## `phage_annotator.ui_qt.services.jobs_part1`

Extracted definitions group 1 for jobs.

Public documented symbols:
- `CancelToken` (class): Thread-safe cancellation token.
- `JobSignals` (class): Qt signals for job lifecycle events.
- `JobHandle` (class): Handle returned from JobManager.submit.
- `JobSnapshot` (class): Immutable summary of one running or queued job.
- `JobTelemetry` (class): Public queue and lifecycle telemetry for diagnostics surfaces.
- `JobRunnable` (class): QRunnable wrapper that emits JobSignals.

## `phage_annotator.ui_qt.services.jobs_part2`

Extracted definitions group 2 for jobs.

Public documented symbols:
- `JobManager` (class): Submit and manage background jobs with GUI-thread callbacks.

## `phage_annotator.ui_qt.services.jobs_part3`

Extracted definitions group 3 for jobs.

## `phage_annotator.ui_qt.services.panel_logging`

Panel-specific action logging helpers.

Public documented symbols:
- `PanelActionLogger` (class): Helper for logging panel-specific actions.
- `set_global_gui_owner` (function): Set the global GUI owner for the unified logging system.
- `get_panel_logger` (function): Get or create a panel-specific logger.
- `log_panel_action` (function): Decorator to automatically log function calls.
- `log_contrast_changes` (function): Log contrast/display value changes.
- `log_annotation_batch` (function): Log batch annotation operations.

## `phage_annotator.ui_qt.services.settings_proxy`

Unified settings proxy bridging QSettings and settings service.

Public documented symbols:
- `UnifiedSettingsProxy` (class): QSettings-compatible wrapper that prefers settings service when available.

## `phage_annotator.ui_qt.services.settings_qt`

Qt-specific SettingsService implementation using QSettings.

Public documented symbols:
- `QSettingsService` (class): QSettings-backed settings service for persistent storage.

## `phage_annotator.ui_qt.services.settings_schema`

Typed UI settings defaults and migration helpers.

Public documented symbols:
- `apply_settings_migrations` (function): Copy known legacy keys forward when new keys are missing.
- `ensure_ui_settings_defaults` (function): Seed deterministic defaults for key GUI settings.

## `phage_annotator.ui_qt.services.status`

Central status models and presenter for the Qt annotation GUI.

## `phage_annotator.ui_qt.services.status_derived`

Derived status builder for the compact status bar and details panel.

## `phage_annotator.ui_qt.services.status_derived_part1`

Extracted definitions group 1 for status_derived.

Public documented symbols:
- `DerivedStatusSnapshot` (class): Structured snapshot shared by compact and detailed status views.

## `phage_annotator.ui_qt.services.status_derived_part2`

Extracted definitions group 2 for status_derived.

Public documented symbols:
- `build_status_snapshot` (function): Build a unified status snapshot from current window/controller state.

## `phage_annotator.ui_qt.services.status_part1`

Extracted definitions group 1 for status.

Public documented symbols:
- `StatusText` (class): Canonical wording for common scientific annotation status states.

## `phage_annotator.ui_qt.services.status_part2`

Extracted definitions group 2 for status.

## `phage_annotator.ui_qt.services.status_part2_part1`

Extracted definitions group 1 for status_part2.

Public documented symbols:
- `StatusMessage` (class): Ephemeral or sticky user-facing status feedback.
- `ActivityStatus` (class): Long-running or workflow-scoped activity shown in the state zone.
- `StatusModel` (class): Derived operational status built from controller/session/view/job state.
- `ManagedStatusBar` (class): Status bar that routes legacy Qt `showMessage()` calls into the presenter.

## `phage_annotator.ui_qt.services.status_part2_part2`

Extracted definitions group 2 for status_part2.

Public documented symbols:
- `StatusService` (class): Own compact status-bar presentation and message/activity prioritization.

## `phage_annotator.ui_qt.services.status_service_part1`

Extracted method group 1 for StatusService.

Public documented symbols:
- `StatusServicePart1` (class): Method group 1 extracted from StatusService.

## `phage_annotator.ui_qt.services.status_service_part2`

Extracted method group 2 for StatusService.

Public documented symbols:
- `StatusServicePart2` (class): Method group 2 extracted from StatusService.

## `phage_annotator.ui_qt.services.thread_qt`

Qt-specific ThreadService implementation using QThreadPool.

Public documented symbols:
- `QtRunnable` (class): QRunnable wrapper for Python functions.
- `QtThreadService` (class): Qt-based thread service using QThreadPool.

## `phage_annotator.ui_qt.utils`

Qt-based UI utilities and helpers.

## `phage_annotator.ui_qt.utils.annotations`

Annotation interaction helpers.

Public documented symbols:
- `AnnotationsMixin` (class): Mixin for annotation add/remove and profile line edits.

## `phage_annotator.ui_qt.utils.annotations_mixin_part1`

Extracted method group 1 for AnnotationsMixin.

Public documented symbols:
- `AnnotationsMixinPart1` (class): Method group 1 extracted from AnnotationsMixin.

## `phage_annotator.ui_qt.utils.annotations_mixin_part2`

Extracted method group 2 for AnnotationsMixin.

Public documented symbols:
- `AnnotationsMixinPart2` (class): Method group 2 extracted from AnnotationsMixin.

## `phage_annotator.ui_qt.utils.bcontrast_integration`

Integration module for keyboard shortcuts and visual indicators into the main window.

Public documented symbols:
- `KeyboardShortcutIntegration` (class): Integration handler for keyboard shortcuts in the main window.
- `VisualIndicatorIntegration` (class): Integration handler for visual indicators in the main window status bar.
- `integrate_b_contrast_features` (function): Main integration point for all B&C features into the main window.

## `phage_annotator.ui_qt.utils.constants`

Shared GUI constants and small helpers.

Public documented symbols:
- `CancelTokenShim` (class): Minimal CancelToken-compatible shim for synchronous jobs.

## `phage_annotator.ui_qt.utils.context_menu`

Annotation context menu actions for near-point editing.

Public documented symbols:
- `ContextMenuMixin` (class): Mixin providing right-click context actions for annotations.

## `phage_annotator.ui_qt.utils.contrast_lut`

Advanced brightness/contrast mapping with pre-computed Look-Up Tables (LUT).

## `phage_annotator.ui_qt.utils.contrast_lut_part1`

Extracted definitions group 1 for contrast_lut.

Public documented symbols:
- `ConverterSetup` (class): Core brightness/contrast mapping engine with LUT pre-computation.

## `phage_annotator.ui_qt.utils.contrast_lut_part2`

Extracted definitions group 2 for contrast_lut.

Public documented symbols:
- `MinMaxGroup` (class): Coupled min/max value pair with validation.
- `computeHistogram` (function): Compute histogram from image data.
- `autoScaleHistogram` (function): Automatically determine optimal min/max range from data.

## `phage_annotator.ui_qt.utils.debug`

Debug logging helpers for GUI internals.

Public documented symbols:
- `debug_log` (function): Log cache/debug messages when DEBUG_CACHE is enabled.

## `phage_annotator.ui_qt.utils.export`

Export and project save/load helpers.

## `phage_annotator.ui_qt.utils.export_mixin_part1`

Extracted method group 1 for ExportMixin.

Public documented symbols:
- `ExportMixinPart1` (class): Method group 1 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part2`

Extracted method group 2 for ExportMixin.

Public documented symbols:
- `ExportMixinPart2` (class): Method group 2 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part3`

Extracted method group 3 for ExportMixin.

Public documented symbols:
- `ExportMixinPart3` (class): Method group 3 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part4`

Extracted method group 4 for ExportMixin.

Public documented symbols:
- `ExportMixinPart4` (class): Method group 4 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part5`

Extracted method group 5 for ExportMixin.

Public documented symbols:
- `ExportMixinPart5` (class): Method group 5 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part6`

Extracted method group 6 for ExportMixin.

Public documented symbols:
- `ExportMixinPart6` (class): Method group 6 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part7`

Extracted method group 7 for ExportMixin.

Public documented symbols:
- `ExportMixinPart7` (class): Method group 7 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part8`

Extracted method group 8 for ExportMixin.

Public documented symbols:
- `ExportMixinPart8` (class): Method group 8 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_mixin_part9`

Extracted method group 9 for ExportMixin.

Public documented symbols:
- `ExportMixinPart9` (class): Method group 9 extracted from ExportMixin.

## `phage_annotator.ui_qt.utils.export_part1`

Extracted definitions group 1 for export.

Public documented symbols:
- `ExportMixin` (class): Mixin for saving/loading annotations and projects.

## `phage_annotator.ui_qt.utils.export_part2`

Extracted definitions group 2 for export.

## `phage_annotator.ui_qt.utils.iconography`

Centralized icon helpers for workflow and tool surfaces.

Public documented symbols:
- `workflow_sidebar_icon` (function): Run the workflow sidebar icon workflow.
- `right_sidebar_icon` (function): Run the right sidebar icon workflow.
- `tool_icon` (function): Run the tool icon workflow.

## `phage_annotator.ui_qt.utils.image_io`

Image metadata and loading helpers for the GUI.

Public documented symbols:
- `DiagnosticArray` (class): NumPy array subclass that can carry lightweight diagnostics metadata.
- `read_metadata` (function): Read lightweight metadata for an image without loading full data.
- `load_array` (function): Load image data and standardize to (T, Z, Y, X).

## `phage_annotator.ui_qt.utils.jobs`

Background job wiring for the GUI.

Public documented symbols:
- `JobsMixin` (class): Mixin for JobManager integration and log handling.

## `phage_annotator.ui_qt.utils.jobs_mixin_part1`

Extracted method group 1 for JobsMixin.

Public documented symbols:
- `JobsMixinPart1` (class): Method group 1 extracted from JobsMixin.

## `phage_annotator.ui_qt.utils.jobs_mixin_part2`

Extracted method group 2 for JobsMixin.

Public documented symbols:
- `JobsMixinPart2` (class): Method group 2 extracted from JobsMixin.

## `phage_annotator.ui_qt.utils.keyboard_shortcut_manager_part1`

Extracted method group 1 for KeyboardShortcutManager.

Public documented symbols:
- `KeyboardShortcutManagerPart1` (class): Method group 1 extracted from KeyboardShortcutManager.

## `phage_annotator.ui_qt.utils.keyboard_shortcut_manager_part2`

Extracted method group 2 for KeyboardShortcutManager.

Public documented symbols:
- `KeyboardShortcutManagerPart2` (class): Method group 2 extracted from KeyboardShortcutManager.

## `phage_annotator.ui_qt.utils.keyboard_shortcuts`

Keyboard shortcuts for rapid modality and display control.

Public documented symbols:
- `KeyboardShortcutManager` (class): Manages keyboard shortcuts for the application.

## `phage_annotator.ui_qt.utils.modality_helpers`

Helper mixin for multi-modality panel integration.

Public documented symbols:
- `ModalityHelpersMixin` (class): Mixin to sync modality lists across analysis panels.

## `phage_annotator.ui_qt.utils.modality_styling`

Visual styling system for active/inactive modality indicators.

Public documented symbols:
- `ModalityStyleScheme` (class): Color scheme and styling constants for modality UI elements.
- `ModalityVisualState` (class): Helper class for managing visual state of a modality indicator widget.

## `phage_annotator.ui_qt.utils.playback`

Playback helpers for high-FPS viewing.

Public documented symbols:
- `PlaybackMixin` (class): Mixin for playback thread handling and frame stepping.

## `phage_annotator.ui_qt.utils.sidebar_manager`

Sidebar layout helpers for canvas-first docking.

Public documented symbols:
- `SidebarLayoutConfig` (class): Layout sizing configuration for left and right sidebars (dock panels).
- `SidebarManager` (class): Compute layout sizes and labels for the sidebar experience.

## `phage_annotator.ui_qt.utils.state`

State proxy and image helpers for the GUI.

Public documented symbols:
- `StateMixin` (class): Mixin for state proxies and image helper utilities.

## `phage_annotator.ui_qt.utils.state_mixin_part1`

Extracted method group 1 for StateMixin.

Public documented symbols:
- `StateMixinPart1` (class): Method group 1 extracted from StateMixin.

## `phage_annotator.ui_qt.utils.state_mixin_part2`

Extracted method group 2 for StateMixin.

Public documented symbols:
- `StateMixinPart2` (class): Method group 2 extracted from StateMixin.

## `phage_annotator.ui_qt.utils.state_mixin_part3`

Extracted method group 3 for StateMixin.

Public documented symbols:
- `StateMixinPart3` (class): Method group 3 extracted from StateMixin.

## `phage_annotator.ui_qt.utils.state_mixin_part4`

Extracted method group 4 for StateMixin.

Public documented symbols:
- `StateMixinPart4` (class): Method group 4 extracted from StateMixin.

## `phage_annotator.ui_qt.utils.state_mixin_part5`

Extracted method group 5 for StateMixin.

Public documented symbols:
- `StateMixinPart5` (class): Method group 5 extracted from StateMixin.

## `phage_annotator.ui_qt.utils.table_status`

Annotation table, status bar, and view stats helpers.

Public documented symbols:
- `TableStatusMixin` (class): Mixin for annotation table and status rendering.

## `phage_annotator.ui_qt.utils.table_status_mixin_part1`

Extracted method group 1 for TableStatusMixin.

Public documented symbols:
- `TableStatusMixinPart1` (class): Method group 1 extracted from TableStatusMixin.

## `phage_annotator.ui_qt.utils.table_status_mixin_part2`

Extracted method group 2 for TableStatusMixin.

Public documented symbols:
- `TableStatusMixinPart2` (class): Method group 2 extracted from TableStatusMixin.

## `phage_annotator.ui_qt.utils.table_status_mixin_part3`

Extracted method group 3 for TableStatusMixin.

Public documented symbols:
- `TableStatusMixinPart3` (class): Method group 3 extracted from TableStatusMixin.

## `phage_annotator.ui_qt.utils.table_status_mixin_part4`

Extracted method group 4 for TableStatusMixin.

Public documented symbols:
- `TableStatusMixinPart4` (class): Method group 4 extracted from TableStatusMixin.

## `phage_annotator.ui_qt.utils.table_status_mixin_part5`

Extracted method group 5 for TableStatusMixin.

Public documented symbols:
- `TableStatusMixinPart5` (class): Method group 5 extracted from TableStatusMixin.

## `phage_annotator.ui_qt.utils.ui_actions`

Menu/action creation helpers for the main window.

Public documented symbols:
- `build_menus` (function): Build menus, actions, and shortcuts for the main window.

## `phage_annotator.ui_qt.utils.ui_annotation_views_mixin_part1`

Extracted method group 1 for UiAnnotationViewsMixin.

Public documented symbols:
- `UiAnnotationViewsMixinPart1` (class): Method group 1 extracted from UiAnnotationViewsMixin.

## `phage_annotator.ui_qt.utils.ui_annotation_views_mixin_part2`

Extracted method group 2 for UiAnnotationViewsMixin.

Public documented symbols:
- `UiAnnotationViewsMixinPart2` (class): Method group 2 extracted from UiAnnotationViewsMixin.

## `phage_annotator.ui_qt.utils.ui_docks`

Dock/panel wiring helpers for the main window.

## `phage_annotator.ui_qt.utils.ui_docks_part1`

Extracted definitions group 1 for ui_docks.

## `phage_annotator.ui_qt.utils.ui_docks_part1_part1`

Extracted definitions group 1 for ui_docks_part1.

## `phage_annotator.ui_qt.utils.ui_docks_part1_part2`

Extracted definitions group 2 for ui_docks_part1.

Public documented symbols:
- `refresh_panel_policy_actions` (function): Synchronize menu quick-policy action check states from policy state.
- `is_panel_auto_open_enabled` (function): Return whether panel auto open enabled is true for the current state.
- `is_panel_auto_open_enabled_for_trigger` (function): Return whether panel auto open enabled for trigger is true for the current state.
- `set_panel_auto_open_enabled` (function): Set panel auto open enabled for the current workflow.
- `set_panel_auto_open_enabled_for_trigger` (function): Set panel auto open enabled for trigger for the current workflow.
- `is_panel_pinned` (function): Return whether panel pinned is true for the current state.
- `set_panel_pinned` (function): Set panel pinned for the current workflow.

## `phage_annotator.ui_qt.utils.ui_docks_part1_part3`

Extracted definitions group 3 for ui_docks_part1.

Public documented symbols:
- `init_panels` (function): Create dock widgets and corresponding View menu actions.
- `get_panel_spec` (function): Return panel spec by id.
- `get_dock` (function): Return the dock widget for a panel id.

## `phage_annotator.ui_qt.utils.ui_docks_part1_part4`

Extracted definitions group 4 for ui_docks_part1.

Public documented symbols:
- `PanelManager` (class): Single entrypoint for panel open/place/raise/flash behavior.
- `open_panel` (function): Open panel by id with canonical placement, raise, and flash.

## `phage_annotator.ui_qt.utils.ui_docks_part1_part5`

Extracted definitions group 5 for ui_docks_part1.

Public documented symbols:
- `build_panel_registry` (function): Return the declarative list of dock panel specs.

## `phage_annotator.ui_qt.utils.ui_docks_part1_part6`

Extracted definitions group 6 for ui_docks_part1.

Public documented symbols:
- `apply_panel_defaults` (function): Reset dock placement/visibility using PanelSpec defaults.
- `create_dock` (function): Create a standard dock widget with common features enabled.
- `wire_dock_action` (function): Keep dock visibility, menu toggle, and optional checkbox in sync.

## `phage_annotator.ui_qt.utils.ui_docks_part2`

Extracted definitions group 2 for ui_docks.

Public documented symbols:
- `get_panel_opened_by` (function): Return panel opened by for the current workflow.
- `make_sidebar_widget` (function): Create sidebar widget for the current workflow.
- `make_annotations_widget` (function): Create annotations widget for the current workflow.
- `make_review_queue_widget` (function): Create review queue widget for the current workflow.
- `make_advanced_settings_widget` (function): Create advanced settings widget for the current workflow.
- `make_status_details_widget` (function): Create status details widget for the current workflow.
- `make_advanced_analysis_widget` (function): Create progressive-disclosure container for advanced assist analysis.

## `phage_annotator.ui_qt.utils.ui_docks_part3`

Extracted definitions group 3 for ui_docks.

Public documented symbols:
- `make_roi_widget` (function): Create roi widget for the current workflow.

## `phage_annotator.ui_qt.utils.ui_docks_part4`

Extracted definitions group 4 for ui_docks.

Public documented symbols:
- `make_roi_manager_widget` (function): Create roi manager widget for the current workflow.
- `make_results_widget` (function): Create results widget for the current workflow.
- `make_recorder_widget` (function): Create recorder widget for the current workflow.
- `make_hist_widget` (function): Create hist widget for the current workflow.
- `make_profile_widget` (function): Create the profile (line-plot) widget and checkbox.
- `make_orthoview_widget` (function): Create orthoview widget for the current workflow.
- `make_smlm_widget` (function): Create smlm widget for the current workflow.
- `make_threshold_widget` (function): Create threshold widget for the current workflow.
- `make_particles_widget` (function): Create particles widget for the current workflow.
- `make_channel_controls_widget` (function): Create the channel controls dock widget.

## `phage_annotator.ui_qt.utils.ui_docks_part5`

Extracted definitions group 5 for ui_docks.

Public documented symbols:
- `make_logs_widget` (function): Create the logs and cache statistics widget.
- `make_metadata_widget` (function): Create metadata widget for the current workflow.
- `make_density_widget` (function): Create density widget for the current workflow.
- `make_qc_issues_widget` (function): Create qc issues widget for the current workflow.

## `phage_annotator.ui_qt.utils.ui_docks_part6`

Extracted definitions group 6 for ui_docks.

Public documented symbols:
- `setup_status_bar` (function): Initialize status-bar widgets (progress, buffer stats, and tool status).

## `phage_annotator.ui_qt.utils.ui_extra`

UI helpers for sidebar, tool routing, layout, and command palette.

Public documented symbols:
- `UiExtrasMixin` (class): Mixin for sidebar pages, tools, and layout/command palette actions.

## `phage_annotator.ui_qt.utils.ui_extra_annotations`

Annotation-view helpers for the main window.

## `phage_annotator.ui_qt.utils.ui_extra_annotations_part1`

Extracted definitions group 1 for ui_extra_annotations.

## `phage_annotator.ui_qt.utils.ui_extra_annotations_part2`

Extracted definitions group 2 for ui_extra_annotations.

Public documented symbols:
- `UiAnnotationViewsMixin` (class): Mixin for lazy-loader-backed annotation view controls.

## `phage_annotator.ui_qt.utils.ui_extra_refresh`

Queued UI refresh helpers for the main window.

Public documented symbols:
- `UiRefreshMixin` (class): Mixin for coalesced GUI refresh scheduling.

## `phage_annotator.ui_qt.utils.ui_extra_tooltips`

Tooltip and event-filter helpers for the main window.

Public documented symbols:
- `UiTooltipMixin` (class): Mixin for delayed tooltips and tooltip cleanup.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part1`

Extracted method group 1 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart1` (class): Method group 1 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part10`

Extracted method group 10 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart10` (class): Method group 10 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part11`

Extracted method group 11 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart11` (class): Method group 11 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part12`

Extracted method group 12 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart12` (class): Method group 12 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part13`

Extracted method group 13 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart13` (class): Method group 13 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part14`

Extracted method group 14 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart14` (class): Method group 14 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part15`

Extracted method group 15 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart15` (class): Method group 15 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part16`

Extracted method group 16 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart16` (class): Method group 16 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part17`

Extracted method group 17 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart17` (class): Method group 17 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part2`

Extracted method group 2 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart2` (class): Method group 2 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part3`

Extracted method group 3 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart3` (class): Method group 3 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part4`

Extracted method group 4 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart4` (class): Method group 4 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part5`

Extracted method group 5 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart5` (class): Method group 5 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part6`

Extracted method group 6 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart6` (class): Method group 6 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part7`

Extracted method group 7 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart7` (class): Method group 7 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part8`

Extracted method group 8 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart8` (class): Method group 8 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_extras_mixin_part9`

Extracted method group 9 for UiExtrasMixin.

Public documented symbols:
- `UiExtrasMixinPart9` (class): Method group 9 extracted from UiExtrasMixin.

## `phage_annotator.ui_qt.utils.ui_setup`

UI construction helpers for the main window.

Public documented symbols:
- `UiSetupMixin` (class): Mixin containing UI construction and dock wiring.

## `phage_annotator.ui_qt.utils.ui_setup_assist`

Focused builders for assist-related UI setup blocks.

Public documented symbols:
- `build_assist_controls` (function): Build assist/ranker controls inside the advanced settings layout.

## `phage_annotator.ui_qt.utils.ui_setup_canvas`

Canvas and table workspace builders for the main UI.

Public documented symbols:
- `build_annotation_table_panel` (function): Build the annotation table side panel.
- `build_canvas_workspace` (function): Build the main figure area and playback bar.

## `phage_annotator.ui_qt.utils.ui_setup_mixin_part1`

Extracted method group 1 for UiSetupMixin.

Public documented symbols:
- `UiSetupMixinPart1` (class): Method group 1 extracted from UiSetupMixin.

## `phage_annotator.ui_qt.utils.ui_setup_mixin_part2`

Extracted method group 2 for UiSetupMixin.

Public documented symbols:
- `UiSetupMixinPart2` (class): Method group 2 extracted from UiSetupMixin.

## `phage_annotator.ui_qt.utils.ui_setup_mixin_part3`

Extracted method group 3 for UiSetupMixin.

Public documented symbols:
- `UiSetupMixinPart3` (class): Method group 3 extracted from UiSetupMixin.

## `phage_annotator.ui_qt.utils.ui_setup_mixin_part4`

Extracted method group 4 for UiSetupMixin.

Public documented symbols:
- `UiSetupMixinPart4` (class): Method group 4 extracted from UiSetupMixin.

## `phage_annotator.ui_qt.utils.ui_setup_panels`

Panel policy builders for the main UI setup mixin.

Public documented symbols:
- `build_panel_policy_controls` (function): Build per-panel auto-open and pin controls in Preferences.
- `refresh_panel_policy_controls` (function): Sync panel policy checkboxes with persisted/current policy state.

## `phage_annotator.ui_qt.utils.ui_setup_registry`

Dock registry and panel-factory helpers for UI setup.

Public documented symbols:
- `UiSetupRegistryMixin` (class): Mixin for dock registry wiring and dock factory wrappers.

## `phage_annotator.ui_qt.utils.ui_setup_registry_mixin_part1`

Extracted method group 1 for UiSetupRegistryMixin.

Public documented symbols:
- `UiSetupRegistryMixinPart1` (class): Method group 1 extracted from UiSetupRegistryMixin.

## `phage_annotator.ui_qt.utils.ui_setup_registry_mixin_part2`

Extracted method group 2 for UiSetupRegistryMixin.

Public documented symbols:
- `UiSetupRegistryMixinPart2` (class): Method group 2 extracted from UiSetupRegistryMixin.

## `phage_annotator.ui_qt.utils.ui_setup_registry_mixin_part3`

Extracted method group 3 for UiSetupRegistryMixin.

Public documented symbols:
- `UiSetupRegistryMixinPart3` (class): Method group 3 extracted from UiSetupRegistryMixin.

## `phage_annotator.ui_qt.utils.ui_setup_workspace`

Workspace-section builders used by the main UI setup mixin.

Public documented symbols:
- `build_modality_loader_section` (function): Build the modality/lazy-loader group used by the Explore page.

## `phage_annotator.ui_qt.utils.validation_hooks`

Real-time validation hooks for automatic QC updates (M6).

Public documented symbols:
- `ValidationHooksMixin` (class): Mixin to add real-time validation hooks to main window.

## `phage_annotator.ui_qt.utils.visual_indicators`

Visual indicators for modality state, sync status, and display settings.

## `phage_annotator.ui_qt.utils.visual_indicators_part1`

Extracted definitions group 1 for visual_indicators.

Public documented symbols:
- `ModalityIndicator` (class): Visual indicator widget for modality state.
- `SyncStateIndicator` (class): Visual indicator for synchronization state.

## `phage_annotator.ui_qt.utils.visual_indicators_part2`

Extracted definitions group 2 for visual_indicators.

Public documented symbols:
- `DisplaySettingsBadge` (class): Compact badge showing active display settings.
- `StatusIndicatorBar` (class): Compact status bar showing all indicators at once.

## `phage_annotator.ui_qt.widgets`

Qt widget exports.

## `phage_annotator.ui_qt.widgets.contrast_dialog`

Brightness and contrast adjustment dialog with histogram preview.

Public documented symbols:
- `ContrastDialog` (class): Dialog for interactive brightness/contrast adjustment.

## `phage_annotator.ui_qt.widgets.contrast_dialog_part1`

Extracted method group 1 for ContrastDialog.

Public documented symbols:
- `ContrastDialogPart1` (class): Method group 1 extracted from ContrastDialog.

## `phage_annotator.ui_qt.widgets.contrast_dialog_part2`

Extracted method group 2 for ContrastDialog.

Public documented symbols:
- `ContrastDialogPart2` (class): Method group 2 extracted from ContrastDialog.

## `phage_annotator.ui_qt.widgets.keyboard_shortcuts_dialog`

Keyboard shortcuts reference dialog.

Public documented symbols:
- `KeyboardShortcutsDialog` (class): Dialog showing all keyboard shortcuts in a searchable table.

## `phage_annotator.ui_qt.widgets.modality_canvas`

Dynamic canvas layout manager for multi-modality views.

## `phage_annotator.ui_qt.widgets.modality_canvas_manager_part1`

Extracted method group 1 for ModalityCanvasManager.

Public documented symbols:
- `ModalityCanvasManagerPart1` (class): Method group 1 extracted from ModalityCanvasManager.

## `phage_annotator.ui_qt.widgets.modality_canvas_manager_part2`

Extracted method group 2 for ModalityCanvasManager.

Public documented symbols:
- `ModalityCanvasManagerPart2` (class): Method group 2 extracted from ModalityCanvasManager.

## `phage_annotator.ui_qt.widgets.modality_canvas_part1`

Extracted definitions group 1 for modality_canvas.

Public documented symbols:
- `LayoutMode` (class): Canvas layout strategies for multiple modalities.
- `ModalityCanvasView` (class): Single canvas view for one modality with associated matplotlib axes.

## `phage_annotator.ui_qt.widgets.modality_canvas_part2`

Extracted definitions group 2 for modality_canvas.

Public documented symbols:
- `ModalityCanvasManager` (class): Dynamic canvas layout manager for multiple modality views.

## `phage_annotator.ui_qt.widgets.modality_fps_control`

Per-modality playback FPS control widget.

Public documented symbols:
- `ModalityFpsControl` (class): Widget providing FPS control for per-modality playback.

## `phage_annotator.ui_qt.widgets.orthoview`

Orthogonal (XZ/YZ) slice views for Z stacks.

Public documented symbols:
- `OrthoViewWidget` (class): XZ/YZ orthogonal viewer with crosshair overlays and click callbacks.

## `phage_annotator.ui_qt.widgets.projection_selector`

Projection selector widget for choosing projection type and axis.

Public documented symbols:
- `ProjectionSelectorWidget` (class): Widget for selecting projection type and axis.

## `phage_annotator.ui_qt.widgets.results_table`

Results table dock widget.

Public documented symbols:
- `ResultsTableWidget` (class): Dock widget for measurement results.

## `phage_annotator.ui_qt.widgets.slider_panel_double`

Dual-handle slider widget for selecting a numeric range.

Public documented symbols:
- `SliderPanelDouble` (class): Dual-handle slider for selecting a min/max range.

## `phage_annotator.ui_qt.workers.qc_background_monitor`

Background QC monitoring worker for continuous quality checks.

Public documented symbols:
- `QCBackgroundMonitor` (class): Background worker that continuously monitors annotation and image quality.
- `QCMonitorStatusWidget` (class): Visual indicator showing background QC monitor status.

## `phage_annotator.utils`

Utilities package.

## `phage_annotator.utils.gpu_utils`

Backward compatibility facade for GPU helpers.

## `phage_annotator.utils.hit_testing`

Hit testing and spatial utilities for context actions (M5).

Public documented symbols:
- `HitTester` (class): Finds nearest annotations to a point.
- `LocalMaxSnapper` (class): Snaps annotations to local maxima in image data.

## `phage_annotator.utils.logger`

Dev-only logging helper for console (and optional GUI hook).

Public documented symbols:
- `get_logger` (function): Return a logger configured for console output.
- `set_level` (function): Update log level for all handlers.
- `attach_gui_handler` (function): Optionally attach a GUI handler (e.g., a dock log view).

## `phage_annotator.utils.memory_profiling`

Memory profiling utilities for zero-copy optimizations.

## `phage_annotator.utils.memory_profiling_part1`

Extracted definitions group 1 for memory_profiling.

Public documented symbols:
- `get_current_memory_mb` (function): Return current process RSS (Resident Set Size) in megabytes.
- `get_peak_memory_mb` (function): Return peak memory usage since process start (platform-dependent).
- `memory_snapshot` (function): Context manager to measure memory delta during a code block.
- `profile_memory` (function): Decorator to profile memory usage of a function.

## `phage_annotator.utils.memory_profiling_part2`

Extracted definitions group 2 for memory_profiling.

Public documented symbols:
- `MemoryTracker` (class): Track memory usage over time with periodic sampling.
- `assert_no_memory_regression` (function): Assert current memory is not significantly higher than baseline.

## `phage_annotator.utils.zero_copy`

Zero-copy array view utilities for memory-efficient operations.

## `phage_annotator.utils.zero_copy_part1`

Extracted definitions group 1 for zero_copy.

Public documented symbols:
- `safe_view` (function): Return a view of the array, optionally marked read-only.
- `readonly_view` (function): Return a read-only view of the array (convenience wrapper for safe_view).
- `ensure_contiguous` (function): Return a contiguous array, copying only if necessary.
- `is_view_of` (function): Check if arr is a view of base (shares memory).
- `memory_size_mb` (function): Return the memory size of array in megabytes.

## `phage_annotator.utils.zero_copy_part2`

Extracted definitions group 2 for zero_copy.

Public documented symbols:
- `ensure_writable` (function): Return a writable copy if array is read-only, otherwise return original.
- `can_avoid_copy` (function): Check if an array operation can avoid copying based on requirements.
- `safe_slice_2d` (function): Extract a 2D slice with bounds checking, returning a safe view.
- `frame_view_4d` (function): Extract a 2D frame from a 4D (T, Z, Y, X) stack as a safe view.

