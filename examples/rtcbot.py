import json

from nio import (
    AsyncClient,
    ClientConfig,
    DevicesError,
    Event,
    InviteEvent,
    LocalProtocolError,
    LoginResponse,
    MatrixRoom,
    MatrixUser,
    RoomMessageText,
    RoomSendResponse,
    CallInviteEvent,
    CallCandidatesEvent,
    crypto,
    exceptions,
)
from aiortc import (
    RTCIceCandidate,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from aiortc.sdp import candidate_from_sdp, candidate_to_sdp

from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder

import os
ROOM_ID = os.environ['ROOM_ID']
from flag import FlagVideoStreamTrack

class RTCBot:
    def __init__(self, nio_client):
        self.nio_client = nio_client
        self.pc = RTCPeerConnection()
        self.recorder = MediaRecorder("recording.mp4")

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"Connection state is {self.pc.connectionState}")
            #if self.pc.connectionState == "failed":
                #await self.pc.close()
                #pcs.discard(pc)

        @self.pc.on("track")
        def on_track(track):
            print("Receiving %s" % track.kind)
            self.recorder.addTrack(track)

    def add_tracks(self):
        self.pc.addTrack(FlagVideoStreamTrack())

    async def cb_call_invite(self, room: MatrixRoom, event: CallInviteEvent):
        """Callback to call invite

        Arguments:
            room {MatrixRoom} -- Provided by nio
            event {CallInviteEvent} -- Provided by nio
        """
        offer_content = event.source["content"]
        print(f"=== OFFER ===\n{json.dumps(offer_content)}\n\n")

        assert offer_content["version"] == "1"
        sdp_offer = offer_content["offer"]["sdp"]

        obj = RTCSessionDescription(type="offer", sdp=sdp_offer)
        await self.pc.setRemoteDescription(obj)
        await self.recorder.start()

        # send answer
        self.add_tracks()
        await self.pc.setLocalDescription(await self.pc.createAnswer())
        sdp_answer = self.pc.localDescription.sdp

        #import pdb
        #pdb.set_trace()

        import pydash
        answer_content = pydash.omit(offer_content, "offer")
        answer_content["answer"] = {"sdp": sdp_answer, "type": "answer"}

        print(f"=== ANSWER ===\n{json.dumps(answer_content)}\n\n")

        try:
            await self.nio_client.room_send(
                room_id=ROOM_ID,
                message_type="m.call.answer",
                content={
                    "msgtype": "m.call.answer",
                    "content": answer_content
                },
            )
        except exceptions.OlmUnverifiedDeviceError as err:
            print("These are all known devices:")
            device_store: crypto.DeviceStore = device_store
            [
                print(
                    f"\t{device.user_id}\t {device.device_id}\t {device.trust_state}\t  {device.display_name}"
                )
                for device in device_store
            ]
            sys.exit(1)


    async def cb_call_candidates(self, room: MatrixRoom, event: CallCandidatesEvent):
        """Callback to call candidates

        Arguments:
            room {MatrixRoom} -- Provided by nio
            event {CallCandidatesEvent} -- Provided by nio
        """
        candidates_content = event.source["content"]
        print(f"=== CANDIDATES ===\n{json.dumps(candidates_content)}\n\n")

        for c in candidates_content['candidates']:
            obj = candidate_from_sdp(c["candidate"].split(":", 1)[1])
            obj.sdpMid = c["sdpMid"]
            obj.sdpMLineIndex = c["sdpMLineIndex"]

            print(f"=== CANDIDATE ===\n{json.dumps(candidate_to_sdp(obj))}\n\n")

            await self.pc.addIceCandidate(obj)
            #break

        #assert offer_content["version"] == "1"
