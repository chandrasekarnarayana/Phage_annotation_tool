// ThunderSTORM bridge macro template for Phage Annotator.
// Inputs via env/placeholder replacement:
// - ${PHAGE_PLUGIN_COMMAND} (or command name in manifest)
// - ${PHAGE_PLUGIN_ARG_STRING}
// - ${PHAGE_SMLM_OUTPUT}

setBatchMode(true);
run("${PHAGE_PLUGIN_COMMAND}", "${PHAGE_PLUGIN_ARG_STRING}");
if ("${PHAGE_SMLM_OUTPUT}" != "") {
    saveAs("Results", "${PHAGE_SMLM_OUTPUT}");
}
