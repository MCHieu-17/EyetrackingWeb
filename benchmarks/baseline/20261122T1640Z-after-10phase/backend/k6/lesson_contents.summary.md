# k6 summary

scenario: lesson_contents

- http_req_failed: rate=0.000
- iterations: count=238.000, rate=23.533
- http_req_connecting: min=0.000, med=0.000, max=0.093, p(90)=0.000, p(95)=0.000, p(99)=0.081, avg=0.002
- http_req_blocked: p(90)=0.015, p(95)=0.025, p(99)=0.105, avg=0.013, min=0.002, med=0.011, max=0.123
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_duration: min=3.127, med=10.796, max=21.730, p(90)=18.677, p(95)=19.092, p(99)=19.426, avg=11.506
- http_req_sending: med=0.040, max=0.203, p(90)=0.049, p(95)=0.053, p(99)=0.099, avg=0.039, min=0.007
- http_req_receiving: min=0.008, med=0.068, max=0.429, p(90)=0.217, p(95)=0.252, p(99)=0.299, avg=0.099
- http_req_duration{expected_response:true}: min=3.127, med=10.796, max=21.730, p(90)=18.677, p(95)=19.092, p(99)=19.426, avg=11.506
- http_req_waiting: med=10.665, max=21.593, p(90)=18.499, p(95)=18.945, p(99)=19.284, avg=11.369, min=3.075
- vus: min=5.000, max=5.000
