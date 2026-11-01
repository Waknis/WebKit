#!/bin/bash
# Regenerates the Web Inspector resources of the prebuilt product from this checkout, and
# writes how TestCombined.js differs from what it was before to the file named by $1.
set -euo pipefail

PRODUCT="$PWD/WebKitBuild/Release"
if [ -d "$PRODUCT/WebInspectorUI.framework/Versions/A/Resources" ]; then
    RES_REL="WebInspectorUI.framework/Versions/A/Resources"
else
    RES_REL="WebInspectorUI.framework/Resources"
fi

# copy-user-interface-resources.pl reads InspectorBackendCommands.js from JavaScriptCore's
# private headers and InspectorNativeFunctionParameters.json from WebCore's.
JSC_HEADERS="$PRODUCT/JavaScriptCore.framework/PrivateHeaders"
if [ ! -f "$JSC_HEADERS/InspectorBackendCommands.js" ]; then
    echo "regen: InspectorBackendCommands.js missing from JavaScriptCore private headers; reused the product's copy" >> ci-notes.txt
    JSC_HEADERS="$RUNNER_TEMP/jsc-headers"
    mkdir -p "$JSC_HEADERS"
    cp "$PRODUCT/$RES_REL/Protocol/InspectorBackendCommands.js" "$JSC_HEADERS/"
fi

COMBINED="$PRODUCT/$RES_REL/TestCombined.js"
cp "$COMBINED" "$RUNNER_TEMP/TestCombined.before.js"

env SRCROOT="$PWD/Source/WebInspectorUI" \
    TARGET_BUILD_DIR="$PRODUCT" \
    BUILT_PRODUCTS_DIR="$PRODUCT" \
    UNLOCALIZED_RESOURCES_FOLDER_PATH="$RES_REL" \
    DERIVED_SOURCES_DIR="$RUNNER_TEMP/WebInspectorUI-DerivedSources" \
    JAVASCRIPTCORE_PRIVATE_HEADERS_DIR="$JSC_HEADERS" \
    WEBCORE_PRIVATE_HEADERS_DIR="$PRODUCT/WebCore.framework/PrivateHeaders" \
    COMBINE_INSPECTOR_RESOURCES=NO \
    COMBINE_TEST_RESOURCES=YES \
    perl Source/WebInspectorUI/Scripts/copy-user-interface-resources.pl

ls -l "$COMBINED" "$PRODUCT/$RES_REL/Test.html"
diff -u "$RUNNER_TEMP/TestCombined.before.js" "$COMBINED" > "$1" || true
echo "regen: $1: $(grep -c '^[-+][^-+]' "$1" || true) changed lines" | tee -a ci-notes.txt
