# k6 summary

scenario: session_contents

- http_req_sending: min=0.007, med=0.040, max=0.314, p(90)=0.051, p(95)=0.058, p(99)=0.135, avg=0.041
- http_req_duration{expected_response:true}: p(95)=18.788, p(99)=24.004, avg=12.165, min=2.741, med=12.038, max=56.532, p(90)=18.250
- http_req_duration: p(95)=18.788, p(99)=24.004, avg=12.165, min=2.741, med=12.038, max=56.532, p(90)=18.250
- iterations: count=238.000, rate=23.445
- http_req_receiving: min=0.015, med=0.072, max=0.423, p(90)=0.201, p(95)=0.242, p(99)=0.342, avg=0.100
- http_req_waiting: med=11.859, max=56.402, p(90)=18.153, p(95)=18.649, p(99)=23.766, avg=12.024, min=2.673
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_connecting: avg=0.002, min=0.000, med=0.000, max=0.085, p(90)=0.000, p(95)=0.000, p(99)=0.080
- http_req_blocked: p(99)=0.109, avg=0.013, min=0.002, med=0.011, max=0.118, p(90)=0.014, p(95)=0.019
