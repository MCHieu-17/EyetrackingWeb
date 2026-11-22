# k6 summary

scenario: session_contents

- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.085, p(90)=0.000, p(95)=0.004, p(99)=0.069
- http_req_sending: med=0.040, max=0.044, p(90)=0.043, p(95)=0.044, p(99)=0.044, avg=0.036, min=0.011
- http_req_duration: p(95)=14.960, p(99)=15.232, avg=10.966, min=2.884, med=12.335, max=15.300, p(90)=14.725
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_waiting: avg=10.815, min=2.827, med=12.164, max=15.151, p(90)=14.579, p(95)=14.806, p(99)=15.082
- iterations: count=20.000, rate=4.715
- http_req_blocked: max=0.119, p(90)=0.013, p(95)=0.022, p(99)=0.099, avg=0.015, min=0.003, med=0.011
- http_req_duration{expected_response:true}: p(95)=14.960, p(99)=15.232, avg=10.966, min=2.884, med=12.335, max=15.300, p(90)=14.725
- http_req_receiving: p(90)=0.170, p(95)=0.195, p(99)=0.211, avg=0.116, min=0.028, med=0.125, max=0.215
- http_req_failed: rate=0.000
- vus: min=1.000, max=1.000
