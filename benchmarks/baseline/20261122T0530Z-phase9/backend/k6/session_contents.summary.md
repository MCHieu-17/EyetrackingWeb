# k6 summary

scenario: session_contents

- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- vus: min=5.000, max=5.000
- iterations: count=238.000, rate=23.593
- http_req_blocked: p(95)=0.015, p(99)=0.110, avg=0.014, min=0.002, med=0.011, max=0.315, p(90)=0.014
- http_req_sending: min=0.007, med=0.040, max=0.182, p(90)=0.051, p(95)=0.058, p(99)=0.082, avg=0.040
- http_req_connecting: min=0.000, med=0.000, max=0.103, p(90)=0.000, p(95)=0.000, p(99)=0.080, avg=0.002
- http_req_waiting: min=2.189, med=9.452, max=19.696, p(90)=16.371, p(95)=17.477, p(99)=18.650, avg=10.571
- http_req_duration: p(99)=18.830, avg=10.711, min=2.233, med=9.531, max=19.836, p(90)=16.468, p(95)=17.655
- http_req_duration{expected_response:true}: avg=10.711, min=2.233, med=9.531, max=19.836, p(90)=16.468, p(95)=17.655, p(99)=18.830
- http_req_failed: rate=0.000
- http_req_receiving: avg=0.100, min=0.009, med=0.069, max=0.403, p(90)=0.218, p(95)=0.257, p(99)=0.356
