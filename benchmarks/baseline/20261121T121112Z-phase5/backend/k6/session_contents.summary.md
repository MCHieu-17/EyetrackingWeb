# k6 summary

scenario: session_contents

- http_req_sending: p(99)=0.116, avg=0.049, min=0.007, med=0.040, max=2.437, p(90)=0.053, p(95)=0.058
- iterations: count=230.000, rate=22.571
- http_req_waiting: avg=20.222, min=4.798, med=21.865, max=42.416, p(90)=27.170, p(95)=28.924, p(99)=38.757
- http_req_receiving: max=0.646, p(90)=0.262, p(95)=0.311, p(99)=0.369, avg=0.127, min=0.030, med=0.094
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_duration: min=4.847, med=22.016, max=42.519, p(90)=27.383, p(95)=29.206, p(99)=39.073, avg=20.397
- http_req_duration{expected_response:true}: p(99)=39.073, avg=20.397, min=4.847, med=22.016, max=42.519, p(90)=27.383, p(95)=29.206
- http_req_blocked: avg=0.013, min=0.002, med=0.011, max=0.124, p(90)=0.015, p(95)=0.021, p(99)=0.116
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.089, p(90)=0.000, p(95)=0.000, p(99)=0.086
