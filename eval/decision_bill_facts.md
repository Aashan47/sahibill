# Bill facts a decision can state (the rules engine input; same fields as E4a)

Top level: `billing_month` "YYYY-MM"; `tou` true/false; `phase` 1 or 3; `sanctioned_load_kw`;
`connected_load_kw`; `mdi_kw`; `reading_date`, `prev_reading_date`, `issue_date`, `due_date`,
`delivery_date` "YYYY-MM-DD"; `units` (units billed in the month); `peak_units`, `offpeak_units`;
`carry_forward_shown` true/false; `snapshot_present` true/false; `snapshot` {"total"|"peak"|"offpeak":
reading}; `present_reading` {same registers: billed reading}; `mf` (multiplying factor);
`snapshot_stamp_date`; `snapshot_geotag` true/false; `mco` true/false; `mco_final_snapshot_present`
true/false; `history` list, most recent first, of {"month": "YYYY-MM", "units": int, "mode": "" or the
code printed, e.g. "DF"}; `status_billed` "lifeline"|"protected"|"unprotected"; `rate_billed` Rs/kWh;
`variable_billed`, `fixed_billed`, `fpa_billed`, `qta_billed` Rs.

`detection` (a detection or theft bill): `units`; `months`; `reasons` "tampering" (meter tampering, slowness,
extra phase, bypass through the meter: CSM 9.2) or "direct_theft" (direct hooking, no meter: CSM 9.1) or null;
`registered` true/false (false only for a person with no connection); `category` "A-1"|"A-2"|"A-3"|"other";
`connected_load_kw`; `already_charged` (units already billed in the detection period, if stated);
`approval` true (CEO or committee approval stated), false (the decision says it was not obtained or not
put on record), null otherwise; `basis` "history"|"future"|"load"|null; `history_credible` true when the
decision shows a usable consumption history for the period before; `period_units` [units of the detection
months in order]; `previous_year_units` [same months one year earlier]; `future_units` [same months after
the checking].

`average` (average billing on a defective meter): `billed_units`; `same_month_last_year`; `last_eleven`
[11 numbers]; `consecutive_months` (months billed on average in a row); `provisional` true only if the
decision says provisional billing (CSM 6.1.5).

`retrieval` (units retrieved from a replaced meter): `defect` "display_wash" or a short word for the
defect; `replaced`, `retrieved`, `debit` as "YYYY-MM" or "YYYY-MM-DD"; `branch` "in_house"|"manufacturer"|null.

`skipped` (skipped charges such as a wrong multiplying factor, raised later): `reason`; `amount`;
`period_from`, `period_to` "YYYY-MM"; `checking` "YYYY-MM" (date of checking or discovery); `raised`
"YYYY-MM" (month the supplementary bill was charged).

`accumulated` (several months' units charged in one bill): `lump_units`; `months_covered`;
`segregated_shown` true/false; `admitted` true when the utility or NEPRA says the units accumulated;
`status` "unprotected"|"protected"|"lifeline" if stated.
