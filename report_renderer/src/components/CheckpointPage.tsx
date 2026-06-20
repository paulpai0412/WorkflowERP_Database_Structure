import { CheckpointPayload } from "../App";
import CheckpointShell from "./CheckpointShell";

interface CheckpointPageProps {
  payload: CheckpointPayload;
}

export default function CheckpointPage({ payload }: CheckpointPageProps) {
  return <CheckpointShell payload={payload} />;
}
