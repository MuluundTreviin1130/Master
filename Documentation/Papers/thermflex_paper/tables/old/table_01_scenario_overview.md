| Scenario | Flex mode | Upper bound active | Lower bound active | Duration [h] | Max events per day | Activation logic | Weather / reference path | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| REF | none | no | no | 0 | 0 | reference dispatch only | Vienna reference weather | Baseline without thermflex activation |
| UPPER_1H | upper_only | yes | no | 1 | 1 | event-response bounded | Vienna reference weather | Main current paper case |
| UPPER_2H | upper_only | yes | no | 2 | 1 | event-response bounded | Vienna reference weather | Duration sensitivity |
| UPPER_4H | upper_only | yes | no | 4 | 1 | event-response bounded | Vienna reference weather | Duration sensitivity |
| LOWER_1C_1H | upper_plus_lower_1C | yes | yes | 1 | 1 | event-response bounded | Vienna reference weather | Optional later sensitivity case |
