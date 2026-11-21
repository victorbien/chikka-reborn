import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ErrorState } from "@/components/shared/ErrorState";
import { RecipientFields } from "@/features/sms/components/RecipientFields";
import { SmsComposer } from "@/features/sms/components/SmsComposer";
import { useCountries } from "@/features/sms/hooks/useSms";
import type { SmsTarget } from "@/features/sms/types";
import { useMe } from "@/features/profile/hooks/useProfile";
import { toUserFacingError } from "@/lib/error-handling";
import { paths } from "@/lib/paths";

const MIN_DIGITS = 5;

/** A first message to a mobile number (or to an SMS contact via ?contact=<id>). */
export function NewSmsForm() {
  const [params] = useSearchParams();
  const contactId = params.get("contact");
  const navigate = useNavigate();
  const countries = useCountries();
  const me = useMe();
  const [chosenCountry, setChosenCountry] = useState<string | null>(null);
  const [number, setNumber] = useState("");

  // The profile country (or the first listed) until the user picks another.
  const available = countries.data;
  const countryCode =
    chosenCountry ??
    (available?.find((c) => c.country_code === me.data?.country_code) ?? available?.[0])
      ?.country_code ??
    "";
  const value = { countryCode, number };

  if (countries.isError && !contactId) {
    const friendly = toUserFacingError(countries.error);
    return (
      <ErrorState
        kind={friendly.kind}
        message={friendly.message}
        requestId={friendly.requestId}
        onRetry={() => void countries.refetch()}
      />
    );
  }

  const digits = value.number.replace(/\D/g, "").length;
  const target: SmsTarget | null = contactId
    ? { kind: "contact", contactId }
    : digits >= MIN_DIGITS && value.countryCode
      ? { kind: "number", to: value.number, countryCode: value.countryCode }
      : null;

  return (
    <div className="space-y-4 p-4">
      <h2 className="text-base font-semibold">New SMS</h2>
      {contactId ? null : countries.isPending ? (
        <p role="status" className="text-sm text-fg-muted">
          Loading countries�
        </p>
      ) : (
        <RecipientFields
          countries={countries.data ?? []}
          value={value}
          onChange={(next) => {
            setChosenCountry(next.countryCode);
            setNumber(next.number);
          }}
        />
      )}
      <SmsComposer
        target={target}
        onSent={(message) => navigate(`${paths.sms}/${message.conversation_id}`)}
      />
    </div>
  );
}
