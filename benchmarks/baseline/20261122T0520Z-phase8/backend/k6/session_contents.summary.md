# k6 summary

scenario: session_contents

- http_req_connecting: max=0.090, p(90)=0.000, p(95)=0.000, p(99)=0.080, avg=0.002, min=0.000, med=0.000
- http_req_duration{expected_response:true}: p(95)=19.100, p(99)=32.479, avg=11.717, min=3.064, med=10.844, max=49.638, p(90)=18.249
- http_req_receiving: p(90)=0.210, p(95)=0.258, p(99)=0.335, avg=0.104, min=0.013, med=0.075, max=0.357
- http_req_waiting: max=49.569, p(90)=18.148, p(95)=18.991, p(99)=32.389, avg=11.573, min=2.989, med=10.677
- http_req_failed: rate=0.000
- iterations: count=238.000, rate=23.501
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_blocked: p(99)=0.103, avg=0.013, min=0.002, med=0.011, max=0.124, p(90)=0.014, p(95)=0.026
- vus: max=5.000, min=5.000
- http_req_duration: avg=11.717, min=3.064, med=10.844, max=49.638, p(90)=18.249, p(95)=19.100, p(99)=32.479
- http_req_sending: p(99)=0.071, avg=0.040, min=0.004, med=0.041, max=0.167, p(90)=0.051, p(95)=0.056
