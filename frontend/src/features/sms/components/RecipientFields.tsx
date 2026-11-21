import { Input, Select } from "@/components/ui/input";
import type { Country } from "@/features/sms/types";

export interface RecipientValue {
  countryCode: string;
  number: string;
}

export interface RecipientFieldsProps {
  countries: Country[];
  value: RecipientValue;
  onChange: (value: RecipientValue) => void;
}

/** Country selector plus the mobile number. Local formats work once a country is chosen. */
export function RecipientFields({ countries, value, onChange }: RecipientFieldsProps) {
  return (
    <fieldset className="grid gap-3 sm:grid-cols-[14rem_1fr]">
      <legend className="mb-1 text-sm font-medium">Send to</legend>
      <div>
        <label htmlFor="sms-country" className="mb-1 block text-sm">
          Country
        </label>
        <Select
          id="sms-country"
          value={value.countryCode}
          onChange={(event) => onChange({ ...value, countryCode: event.target.value })}
        >
          {countries.map((country) => (
            <option key={country.country_code} value={country.country_code}>
              {country.country_name} (+{country.dial_code})
            </option>
          ))}
        </Select>
      </div>
      <div>
        <label htmlFor="sms-number" className="mb-1 block text-sm">
          Mobile number
        </label>
        <Input
          id="sms-number"
          type="tel"
          inputMode="tel"
          autoComplete="off"
          placeholder="0917 123 4567"
          value={value.number}
          onChange={(event) => onChange({ ...value, number: event.target.value })}
          aria-describedby="sms-number-hint"
        />
        <p id="sms-number-hint" className="mt-1 text-xs text-fg-muted">
          Type it the way you would dial it in that country, or start with + and the country code.
        </p>
      </div>
    </fieldset>
  );
}
