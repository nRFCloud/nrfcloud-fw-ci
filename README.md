# CI Repository for nRF Cloud FW
This repo contains the CI setup for building nRF Cloud firmware samples and running them on-device.

Much of this setup is borrowed from the [Asset Tracker Template](https://github.com/nrfconnect/Asset-Tracker-Template).
Both building and running of tests is done on GitHub self-hosted runners.

The build workflow includes a caching mechanism that will look up stored artifacts in a retained folder inside the runner.
As long as the inputs to the build and the version of the build workflow match, building is skipped entirely and artifacts are reused.

## Structure

The `.github/workflows` folder contains all relevant workflow files.

KConfig fragments for compiling the samples can be found in the `config_fragments` folder. It contains KConfigs specific to different cloud stages in the `stages_*` folders. KConfigs specific to the `nrf_cloud_multi_service` sample can be found in the `mss` folder.

The `provision_device` folder contains app and modem firmware for the various supported boards. The `provision.sh` script is used to create and register certificates for all the stages.

Various helper scripts can be found in the `scripts` folder. It also contains a GnuPG public key to encrypt modem traces. The corresponding private key `nrf-cloud-ci-prv.pgp` is shared internally. Encrypting modem traces is necessary since they contain usable login credentials. The `decode_trace.sh` script can be used to decrypt and decode multiple traces at once.

The `tests/on_target` folder contains the test setup. It's based on `pytest` and makes use of various helper libraries contained in its `utils` folder.
For example, flashing DKs is done using `nrfutil-device` and its on-board J-Link, while for Thingys, the included CMSIS-DAP probe is used with `pyocd`.

# Adding a sample

Samples are devided into groups to provide some granularity for running only a subset of tests.
If you intend to create a new group (e.g. `basic-samples`), just create a new step in the `build.yml` workflow:

```yaml
      - name: Build basic samples
        if: inputs.group == 'basic-samples' && steps.cache-check.outputs.cache-hit == 'false'
        shell: bash
```

In that step, add the `west build` command like seen in the other builds:

```bash
            west build -b thingy91x/nrf9151/ns --build-dir $VERSION/thingy91x-hello-world        zephyr/samples/basic/hello_world  -- -DEXTRA_CONF_FILE=$COAP_SERVER_FRAGMENT -Dhello_world_SNIPPET=nrf91-modem-trace-uart
```

The server fragments configure URLs and sectags accordingly. Build artifacts placed with correct naming will be automatically picked up in the artifact upload and caching steps. Modem tracing should be enabled by default to make debugging easier.

Once the build is added, it can be referenced in a `fixture` in `conftest.py`:

```python
@pytest.fixture(scope="session")
def hello_world_hex_file():
    return find_hex_file("hello_world") or pytest.skip("HEX file not found")
```

A functional test can be created in `tests/on_target/tests/test_functional/test_<some name>`. Taking the fixture as a parameter makes sure the test is only run when the HEX file is available.

Tests usually start with flashing the HEX file and resetting the modem:

```python
def test_hello_world(dut_fota, hello_world_hex_file):
    flash_device(os.path.abspath(coap_cell_location_hex_file))
    dut_cloud.uart.xfactoryreset() # write XFACTORYRESET AT command to make sure the modem is in a clean state
    dut_cloud.uart.flush()

    test_start_time = time.time()
    reset_device()
```

## Debugging CI failures

Begin with figuring out what kind of failure you see:
* building fails -> SDK/workflow issue
* cannot program device, USB error etc. -> CI/device issue
* device doesn't connect to network -> CI/device issue
* program crashes on-device -> possibly SDK/workflow issue
* interaction with cloud fails -> possibly cloud issue
* test condition not met, e.g. timeout -> needs further investigation

Investigating both the logs in the GitHub actions themselves as well as inside the test reports can prove useful.
Examining the modem traces can reveal changed behavior as well. Note that modem traces on nRF9160 are not decrypting the TLS traffic.
Cloud issues can be identified by consistent failures with FW versions that worked before.
CI/device issues are usually specific to one device or device type. Having multiple devices of the same type can help identifying these.
SDK issues only happen in specific SDK versions. Bisect if possible to find the offending commit and request help from the author.
Workflow issues should be identified early when making changes to the workflows here.
