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
cp $BUILD_DIR/dfu_application.zip $TARGET_DIR
cp $BUILD_DIR/dfu_mcuboot.zip $TARGET_DIR
cp $BUILD_DIR/partitions.yml $TARGET_DIR
cp $BUILD_DIR/build_info.yml $TARGET_DIR
cp $BUILD_DIR/merged*.hex $TARGET_DIR
cp $BUILD_DIR/zephyr/.config $TARGET_DIR/zephyr-dotconfig.txt
cp $BUILD_DIR/$SAMPLE_NAME/zephyr/.config $TARGET_DIR/app-dotconfig.txt
cp $BUILD_DIR/$SAMPLE_NAME/zephyr/.config.sysbuild $TARGET_DIR/app-dotconfig.sysbuild.txt
cp $BUILD_DIR/$SAMPLE_NAME/zephyr/zephyr.signed.hex $TARGET_DIR
cp $BUILD_DIR/$SAMPLE_NAME/zephyr/zephyr.dts $TARGET_DIR
cp $BUILD_DIR/$SAMPLE_NAME/zephyr/zephyr.elf $TARGET_DIR
cp $BUILD_DIR/$SAMPLE_NAME/zephyr/log_dictionary.json $TARGET_DIR

exit 0
