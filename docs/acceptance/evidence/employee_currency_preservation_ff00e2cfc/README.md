# Currency preservation repair — source ff00e2cfc

The independent CAD→USD relabelling defect is closed. A mapped currency
column is preserved as observed evidence; conflicts, malformed values and
mixed currencies refuse before arithmetic or completion. No implicit FX or
default substitution is applied over known source currency.

Controls cover:

- uniform USD positive and uniform CAD positive under a CAD job;
- uniform CAD under a USD request refused;
- mixed USD/CAD refused;
- malformed currency refused;
- mapped currency plus supplied default refused;
- missing currency mapping inherits only the explicit job currency;
- currency changed after compilation refuses through the real executor with
  no calculated value and no completion;
- empty mapped unit/pack-size/price-basis values refuse instead of defaulting.

Evidence: `independent-currency-probe.log` (2/2) and `focused-tests.log`
(173 passed), both run on `ff00e2cfc`.
