# k6 summary

scenario: session_contents

- http_req_duration{expected_response:true}: max=62.532, p(90)=18.009, p(95)=18.555, p(99)=21.321, avg=12.667, min=2.586, med=12.666
- http_req_connecting: max=0.099, p(90)=0.000, p(95)=0.000, p(99)=0.094, avg=0.002, min=0.000, med=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_blocked: avg=0.013, min=0.001, med=0.011, max=0.136, p(90)=0.014, p(95)=0.015, p(99)=0.120
- http_req_sending: p(95)=0.056, p(99)=0.091, avg=0.040, min=0.005, med=0.040, max=0.332, p(90)=0.050
- vus: min=5.000, max=5.000
- http_req_receiving: min=0.022, med=0.101, max=0.576, p(90)=0.212, p(95)=0.230, p(99)=0.305, avg=0.112
- http_req_failed: rate=0.000
- iterations: count=238.000, rate=23.376
- http_req_duration: avg=12.667, min=2.586, med=12.666, max=62.532, p(90)=18.009, p(95)=18.555, p(99)=21.321
- http_req_waiting: p(99)=21.058, avg=12.516, min=2.544, med=12.531, max=62.438, p(90)=17.904, p(95)=18.468
