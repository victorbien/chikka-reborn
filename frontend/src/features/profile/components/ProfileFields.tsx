import { useMemo } from "react";
import type { UseFormRegisterReturn } from "react-hook-form";
import { FormField } from "@/components/common/FormField";
import { Select } from "@/components/ui/input";
import { countryOptions, LANGUAGES, timeZones } from "@/features/profile/reference";

export interface LocaleFieldsProps {
  country: UseFormRegisterReturn;
  language: UseFormRegisterReturn;
  timeZone: UseFormRegisterReturn;
  errors: { country?: string; language?: string; timeZone?: string };
}

/** Country, language and time zone selects, shared by onboarding and settings. */
export function LocaleFields({ country, language, timeZone, errors }: LocaleFieldsProps) {
  const countries = useMemo(() => countryOptions(), []);
  const zones = useMemo(() => timeZones(), []);
  return (
    <>
      <FormField label="Country" error={errors.country}>
        <Select {...country}>
          <option value="">Prefer not to say</option>
          {countries.map((option) => (
            <option key={option.code} value={option.code}>
              {option.label}
            </option>
          ))}
        </Select>
      </FormField>
      <FormField label="Preferred language" error={errors.language}>
        <Select {...language}>
          {LANGUAGES.map((option) => (
            <option key={option.code} value={option.code} lang={option.code}>
              {option.label}
            </option>
          ))}
        </Select>
      </FormField>
      <FormField label="Time zone" error={errors.timeZone}>
        <Select {...timeZone}>
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
      </FormField>
    </>
  );
}
