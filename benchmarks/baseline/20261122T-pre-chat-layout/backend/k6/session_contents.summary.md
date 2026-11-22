# k6 summary

scenario: session_contents

- http_req_duration: med=11.473, max=21.408, p(90)=17.200, p(95)=18.428, p(99)=19.700, avg=11.097, min=2.805
- http_req_duration{expected_response:true}: max=21.408, p(90)=17.200, p(95)=18.428, p(99)=19.700, avg=11.097, min=2.805, med=11.473
- vus: min=5.000, max=5.000
- http_req_failed: rate=0.000
- http_req_blocked: avg=0.013, min=0.003, med=0.011, max=0.149, p(90)=0.014, p(95)=0.022, p(99)=0.114
- http_req_connecting: p(99)=0.083, avg=0.002, min=0.000, med=0.000, max=0.085, p(90)=0.000, p(95)=0.000
- http_req_sending: p(99)=0.081, avg=0.038, min=0.008, med=0.039, max=0.109, p(90)=0.051, p(95)=0.058
- iterations: count=238.000, rate=23.546
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: p(99)=19.596, avg=10.957, min=2.774, med=11.306, max=21.239, p(90)=17.116, p(95)=18.284
- http_req_receiving: p(99)=0.319, avg=0.102, min=0.020, med=0.073, max=0.351, p(90)=0.217, p(95)=0.273
