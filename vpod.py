#!python3
import subprocess
import json
import os
import random
import time
from vastai_sdk import VastAI


SSH_TARGET_NAME = "vast"
WS_LOCAL_PREFIX = os.path.expanduser("~/work/")
WS_REMOTE_PREFIX = "/home/devpod/work/"


SSH_CONFIG_TEMPLATE = """
Host vast
    HostName {ssh_host}
    Port {ssh_port}
    User root
    LocalForward 8080 localhost:8080
"""

ONSTART_CMD = """
touch ~/.no_auto_tmux
"""


def run(cmd: str):
    return subprocess.check_output(cmd, shell=True).decode("utf-8")


# def find_offers(sdk: VastAI, **kwargs):
#     query = " ".join(f"{k}={v}" for k, v in kwargs.items())
#     return sdk.search_offers(query=query)


# def find_best_offer(sdk: VastAI, gpu_name: str = "RTX_3080", num_gpus=1):
#     return find_offers(sdk, gpu_name=gpu_name, num_gpus=num_gpus)[0]



def offer_repr(offer: dict):
    s = f"{len(offer['gpu_ids'])} x {offer['gpu_name']}"
    s += f" (CUDA {offer['cuda_max_good']})"
    s += f" for ${offer['dph_total']:.2f}/hr"
    return s


def sync_workspace(workspace: str, up=True):
    local = os.path.join(WS_LOCAL_PREFIX, workspace)
    remote = f"{SSH_TARGET_NAME}:" + os.path.join(WS_REMOTE_PREFIX, workspace)
    run(f"ssh {SSH_TARGET_NAME} mkdir -p {WS_REMOTE_PREFIX}")
    if up:
        run(f"rsync -avz {local}/ {remote}")
    else:
        run(f"rsync -avz {remote} {local}")


def start(image: str, query: str, workspace: str | None = None):
    sdk = VastAI()
    # find an offer
    offers = sdk.search_offers(query=query)
    offer = offers[random.randint(0, len(offers[:5]))]
    print(f"Renting {offer_repr(offer)}")
    # launch instance
    resp = sdk.create_instance(id=offer["id"], image=image, onstart_cmd=ONSTART_CMD)
    if not resp["success"]:
        raise ValueError(f"Failed to rent!")
    instance_id = resp["new_contract"]
    instance = sdk.show_instance(id=instance_id)
    status = instance["actual_status"]
    while status is None or status == "loading":
        print("loading...")
        time.sleep(1)
        instance = sdk.show_instance(id=instance_id)
        status = instance["actual_status"]
    # set up SSH
    ssh_host = instance["ssh_host"]
    ssh_port = instance["ssh_port"]
    with open(os.path.expanduser("~/.ssh/config.d/vast"), "w") as fp:
        config = SSH_CONFIG_TEMPLATE.format(ssh_host=ssh_host, ssh_port=ssh_port)
        fp.write(config)
    run(f"ssh-keygen -R '[{ssh_host}]:{ssh_port}' | true")  # remove old occurrences
    run(f"ssh-keyscan -p {ssh_port} {ssh_host} >> ~/.ssh/known_hosts")     # add this host to known
    if workspace is not None:
        sync_workspace(workspace, up=True)
    return instance


def stop():
    sdk = VastAI()
    instances = sdk.show_instances()
    if len(instances) == 0:
        raise ValueError("No instances are running")
    if len(instances) > 1:
        raise ValueError(
            f"Expected exactly 1 running instance, " +
            f"but instead found {len(instances)}"
        )
    sdk.destroy_instance(id=instances[0]["id"])



def main():
    image = "faithlessfriend/equilibrium:dev"
    query = "gpu_name=RTX_3080 num_gpus=1"
    workspace = "equilibrium"
    instance = start(image, query, workspace)
    stop()

    # TODO: create real instance and check actual error (current one is due to non-existing ID)

    sdk = VastAI()
    resp = sdk.create_instance(id=15530478, )
    instance = sdk.show_instance(id=resp["new_contract"])
    print(f"{instance['ssh_host']}:{instance['ssh_port']}")
    # s = sdk.ssh_url(id=r["new_contract"])

    req_url = "https://console.vast.ai/api/v0/instances?owner=me&api_key=876f578cec5365c77718045660b78a47b738dcdbc9bb147f500ff06355d7b35a"

    import sys
    import os

    sys.stdout = os.fdopen(1, 'w')
    sys.stderr = os.fdopen(2, 'w')


    import argparse
    args = argparse.Namespace(api_key=sdk.api_key, id=1234, url="https://console.vast.ai/api/v0")

    self = sdk
    kwargs = {"id": 15530478}

    method_name = "ssh_url"
    arg_details = self.imported_methods.get(method_name, {})
    for arg, details in arg_details.items():
        if details["required"] and arg not in kwargs:
            raise ValueError(f"Missing required argument: {arg}")
        if (
            arg in kwargs
            and details.get("choices") is not None
            and kwargs[arg] not in details["choices"]
        ):
            raise ValueError(
                f"Invalid choice for {arg}: {kwargs[arg]}. Valid options are {details['choices']}"
            )
        kwargs.setdefault(arg, details["default"])

    kwargs.setdefault("api_key", self.api_key)
    kwargs.setdefault("url", self.server_url)
    kwargs.setdefault("retry", self.retry)
    kwargs.setdefault("raw", self.raw)
    kwargs.setdefault("explain", self.explain)
    kwargs.setdefault("quiet", self.quiet)

# GPU_NAME=RTX_3080

# OFFERS=$(vastai search offers 'num_gpus = 1 gpu_name = ${GPU_NAME}')