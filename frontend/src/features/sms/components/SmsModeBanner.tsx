import { Link } from "react-router-dom";
import { LiveBadge, SimulatedBadge } from "@/components/shared/ChannelBadge";
import { useSmsStatus } from "@/features/sms/hooks/useSms";
import { paths } from "@/lib/paths";

/** Always visible on SMS screens: which mode is running, and whether you can send. Simulated
 *  and live are never ambiguous (FR-SMS-003). */
export function SmsModeBanner() {
  const status = useSmsStatus();
  if (!status.data) return null;
  const { is_simulated: simulated, notice, outbound_paused: paused, sender_verified } = status.data;
  return (
    <div
      role="status"
      className="mb-4 flex flex-wrap items-center gap-2 rounded-panel border border-border bg-surface p-3 text-sm"
    >
      {simulated ? <SimulatedBadge /> : <LiveBadge />}
      <span>{notice}</span>
      {paused ? (
        <span className="w-full text-danger">Sending is paused by an administrator.</span>
      ) : null}
      {!sender_verified ? (
        <span className="w-full">
          Verify your mobile number in{" "}
          <Link className="underline" to={paths.settings}>
            Settings
          </Link>{" "}
          to send SMS.
        </span>
      ) : null}
    </div>
  );
}
