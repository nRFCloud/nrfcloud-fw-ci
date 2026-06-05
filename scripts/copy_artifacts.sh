#!/usr/bin/env bash

# take three args, build_dir, artifacts_dir

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 build_dir artifacts_dir"
    exit 1
fi

BUILD_DIR=$1
ARTIFACTS_DIR=$2
BUILD_BASENAME=$(basename $BUILD_DIR)
TARGET_DIR=$ARTIFACTS_DIR/$BUILD_BASENAME

copy_if_exists() {
    src=$1
    dst_dir=$2
    dst_name=$3

    if [ -f "$src" ]; then
        if [ -n "$dst_name" ]; then
            cp "$src" "$dst_dir/$dst_name"
        else
            cp "$src" "$dst_dir"
        fi
    fi
}

# Read the first line of the domains file
first_line=$(head -n 1 "$BUILD_DIR/domains.yaml")

# Check if it starts with "default: "
if [[ "$first_line" == default:\ * ]]; then
    # Extract everything after "default: "
    SAMPLE_NAME="${first_line#default: }"
else
    exit 1
fi

mkdir -p $TARGET_DIR

APP_BASE_DIR="$BUILD_DIR"
if [ -d "$BUILD_DIR/$SAMPLE_NAME/zephyr" ]; then
    APP_BASE_DIR="$BUILD_DIR/$SAMPLE_NAME"
fi

APP_ZEPHYR_DIR="$APP_BASE_DIR/zephyr"
APP_TFM_DIR="$APP_BASE_DIR/tfm"

copy_if_exists "$BUILD_DIR/dfu_application.zip" "$TARGET_DIR"
copy_if_exists "$BUILD_DIR/dfu_mcuboot.zip" "$TARGET_DIR"
copy_if_exists "$BUILD_DIR/partitions.yml" "$TARGET_DIR"
copy_if_exists "$BUILD_DIR/build_info.yml" "$TARGET_DIR"

# Some sysbuild configurations no longer emit merged.hex by default.
# Recreate it from the same images that are flashed in CI.
merge_input_files=(
    "$BUILD_DIR/signed_by_b0_mcuboot.hex"
    "$BUILD_DIR/b0/zephyr/zephyr.hex"
    "$BUILD_DIR/signed_by_b0_mcuboot_s1_variant.hex"
    "$APP_ZEPHYR_DIR/zephyr.signed.hex"
    "$BUILD_DIR/app_provision.hex"
)

can_merge_hex=true
for hex_file in "${merge_input_files[@]}"; do
    if [ ! -f "$hex_file" ]; then
        can_merge_hex=false
        break
    fi
done

if [ "$can_merge_hex" = true ]; then
    MERGEHEX_SCRIPT=""
    if [ -n "$ZEPHYR_BASE" ] && [ -f "$ZEPHYR_BASE/scripts/build/mergehex.py" ]; then
        MERGEHEX_SCRIPT="$ZEPHYR_BASE/scripts/build/mergehex.py"
    elif command -v west >/dev/null 2>&1; then
        WEST_TOPDIR=$(west topdir 2>/dev/null)
        if [ -n "$WEST_TOPDIR" ] && [ -f "$WEST_TOPDIR/zephyr/scripts/build/mergehex.py" ]; then
            MERGEHEX_SCRIPT="$WEST_TOPDIR/zephyr/scripts/build/mergehex.py"
        fi
    fi

    if [ -n "$MERGEHEX_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        if ! python3 "$MERGEHEX_SCRIPT" -o "$BUILD_DIR/merged.hex" "${merge_input_files[@]}"; then
            echo "Error: failed to generate merged.hex"
            exit 1
        fi
    else
        echo "Warning: mergehex.py or python3 not found; skipping merged.hex generation"
    fi
fi

# Fallback: create merged.hex from best available image when full sysbuild merge is not possible.
if [ ! -f "$BUILD_DIR/merged.hex" ]; then
    fallback_inputs=(
        "$BUILD_DIR/signed_by_b0_mcuboot.hex"
        "$BUILD_DIR/b0/zephyr/zephyr.hex"
        "$BUILD_DIR/signed_by_b0_mcuboot_s1_variant.hex"
        "$APP_ZEPHYR_DIR/zephyr.signed.hex"
        "$APP_ZEPHYR_DIR/zephyr.hex"
        "$BUILD_DIR/app_provision.hex"
        "$BUILD_DIR/zephyr/zephyr.signed.hex"
        "$BUILD_DIR/zephyr/zephyr.hex"
    )

    existing_fallback_inputs=()
    for hex_file in "${fallback_inputs[@]}"; do
        if [ -f "$hex_file" ]; then
            existing_fallback_inputs+=("$hex_file")
        fi
    done

    if [ "${#existing_fallback_inputs[@]}" -ge 2 ] && [ -n "$MERGEHEX_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        if ! python3 "$MERGEHEX_SCRIPT" -o "$BUILD_DIR/merged.hex" "${existing_fallback_inputs[@]}"; then
            echo "Warning: failed to create fallback merged.hex"
        fi
    elif [ "${#existing_fallback_inputs[@]}" -ge 1 ]; then
        cp "${existing_fallback_inputs[0]}" "$BUILD_DIR/merged.hex"
    fi
fi

shopt -s nullglob
merged_hex_files=("$BUILD_DIR"/merged*.hex)
for merged_hex in "${merged_hex_files[@]}"; do
    cp "$merged_hex" "$TARGET_DIR"
done
shopt -u nullglob

# Pack additional hex artifacts when present.
extra_hex_files=(
    "$BUILD_DIR/app_provision.hex"
    "$BUILD_DIR/b0/zephyr/zephyr.hex"
    "$BUILD_DIR/mcuboot/zephyr/zephyr.hex"
    "$BUILD_DIR/mcuboot_s1_variant/zephyr/zephyr.hex"
    "$APP_TFM_DIR/api_ns/bin/tfm_s.hex"
    "$APP_TFM_DIR/bin/tfm_s.hex"
    "$APP_ZEPHYR_DIR/tfm_merged.hex"
    "$APP_ZEPHYR_DIR/zephyr.hex"
    "$APP_ZEPHYR_DIR/zephyr.signed.hex"
    "$BUILD_DIR/signed_by_b0_mcuboot.hex"
    "$BUILD_DIR/signed_by_b0_mcuboot_s1_variant.hex"
    "$BUILD_DIR/signed_by_mcuboot_and_b0_mcuboot.hex"
    "$BUILD_DIR/signed_by_mcuboot_and_b0_mcuboot_s1_variant.hex"
)

for hex_file in "${extra_hex_files[@]}"; do
    if [ -f "$hex_file" ]; then
        cp "$hex_file" "$TARGET_DIR"
    fi
done

copy_if_exists "$BUILD_DIR/zephyr/.config" "$TARGET_DIR" "zephyr-dotconfig.txt"
copy_if_exists "$APP_ZEPHYR_DIR/.config" "$TARGET_DIR" "app-dotconfig.txt"
copy_if_exists "$APP_ZEPHYR_DIR/.config.sysbuild" "$TARGET_DIR" "app-dotconfig.sysbuild.txt"
copy_if_exists "$APP_ZEPHYR_DIR/zephyr.signed.hex" "$TARGET_DIR"
copy_if_exists "$APP_ZEPHYR_DIR/zephyr.dts" "$TARGET_DIR"
copy_if_exists "$APP_ZEPHYR_DIR/log_dictionary.json" "$TARGET_DIR"

exit 0
