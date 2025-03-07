#!python3
import subprocess
import argparse
import json
import os
import random
import time
from vastai_sdk import VastAI


SSH_TARGET_NAME = "vast"
WS_LOCAL_PREFIX = os.path.expanduser("~/work/")
WS_REMOTE_PREFIX = "/home/devpod/work/"

STATE_FILE = os.path.expanduser("~/.config/vpod_state.json")


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
        run(f"rsync -avz {remote}/ {local}")


def update_ssh_config(ssh_host: str, ssh_port: int):
    with open(os.path.expanduser("~/.ssh/config.d/vast"), "w") as fp:
        config = SSH_CONFIG_TEMPLATE.format(ssh_host=ssh_host, ssh_port=ssh_port)
        fp.write(config)
    attempts = 3
    success = False
    while not success and attempts > 0:
        try:
            run(f"ssh-keygen -R '[{ssh_host}]:{ssh_port}' | true")  # remove old occurrences
            run(f"ssh-keyscan -p {ssh_port} {ssh_host} >> ~/.ssh/known_hosts")     # add this host to known
            success = True
        except:
            attempts -= 1
            if attempts == 0:
                raise
            else:
                print("Failed to update host keys, retrying in 3 seconds...")
                time.sleep(3)


def start(image: str, query: str, workspace: str | None = None):
    sdk = VastAI()

    # find an offer
    offers = sdk.search_offers(query=query)
    offer = offers[random.randint(0, len(offers[:5]))]
    print(f"Renting {offer_repr(offer)}")

    # launch instance
    resp = sdk.create_instance(id=offer["id"], image=image, onstart_cmd=ONSTART_CMD)
    print("Instances UI: https://cloud.vast.ai/instances/")
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
    update_ssh_config(instance["ssh_host"], instance["ssh_port"])
    if workspace is not None:
        sync_workspace(workspace, up=True)

    # save state
    with open(STATE_FILE, "w") as fp:
        json.dump({"instance_id": instance["id"], "workspace": workspace}, fp)
    return instance


def stop():
    sdk = VastAI()
    with open(STATE_FILE) as fp:
        state = json.load(fp)
    instances = sdk.show_instances()
    if len(instances) == 0:
        raise ValueError("No instances are running")
    if len(instances) > 1:
        raise ValueError(
            f"Expected exactly 1 running instance, " +
            f"but instead found {len(instances)}"
        )
    if instances[0]["id"] != state["instance_id"]:
        raise ValueError(
            f"Inconsistent state: instance_id in state file is {state['instance_id']}, " +
            f"but running instance with id {instances[0]['id']}"
        )
    workspace = state["workspace"]
    if workspace:
        sync_workspace(workspace, up=False)
    sdk.destroy_instance(id=instances[0]["id"])




def main():
    parser = argparse.ArgumentParser("Manage devpods on vast.ai")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # START
    start_parser = subparsers.add_parser("start", help="Start a devpod")
    start_parser.add_argument("image", type=str, help="Image to run on the devpod")
    start_parser.add_argument("query", type=str, help="Vast.ai VM query, e.g. 'gpu_name=RTX_3090 num_gpus=1'")
    start_parser.add_argument("workspace", type=str, help="Name of the workspace (in `~/work/`) to upload to the devpod")

    # STOP
    stop_parser = subparsers.add_parser("stop", help="Stop the currently running devpod")
    # stop_parser.add_argument("w", type=int, help="Argument w")

    args = parser.parse_args()
    if args.command == "start":
        start(args.image, args.query, args.workspace)
    elif args.command == "stop":
        stop()


if __name__ == "__main__" and "__file__" in globals():
    main()


###########################################################

def repl():
    image = "faithlessfriend/equilibrium:dev"
    query = "gpu_name=RTX_3080 num_gpus=1"
    workspace = "equilibrium"
    instance = start(image, query, workspace)
    stop()