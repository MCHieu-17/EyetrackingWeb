# k6 summary

scenario: replay

- http_req_connecting: p(95)=0.004, p(99)=0.057, avg=0.004, min=0.000, med=0.000, max=0.071, p(90)=0.000
- vus: min=1.000, max=1.000
- http_req_sending: avg=0.046, min=0.011, med=0.042, max=0.094, p(90)=0.055, p(95)=0.087, p(99)=0.093
- http_req_duration: avg=9.111, min=2.777, med=9.818, max=12.820, p(90)=12.300, p(95)=12.504, p(99)=12.757
- iterations: count=20.000, rate=4.757
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: med=9.384, max=12.493, p(90)=12.076, p(95)=12.318, p(99)=12.458, avg=8.901, min=2.729
- http_req_receiving: avg=0.164, min=0.029, med=0.148, max=0.373, p(90)=0.358, p(95)=0.361, p(99)=0.370
- http_req_failed: rate=0.000
- http_req_blocked: p(95)=0.026, p(99)=0.086, avg=0.016, min=0.003, med=0.011, max=0.101, p(90)=0.015
- http_req_duration{expected_response:true}: p(95)=12.504, p(99)=12.757, avg=9.111, min=2.777, med=9.818, max=12.820, p(90)=12.300
