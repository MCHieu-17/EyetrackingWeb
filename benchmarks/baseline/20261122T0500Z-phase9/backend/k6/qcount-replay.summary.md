# k6 summary

scenario: replay

- http_req_connecting: p(99)=0.064, avg=0.004, min=0.000, med=0.000, max=0.079, p(90)=0.000, p(95)=0.004
- iterations: rate=4.637, count=20.000
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_blocked: min=0.003, med=0.011, max=0.110, p(90)=0.017, p(95)=0.027, p(99)=0.094, avg=0.017
- http_req_sending: med=0.043, max=0.072, p(90)=0.054, p(95)=0.068, p(99)=0.071, avg=0.045, min=0.012
- http_req_duration: avg=14.497, min=6.841, med=15.933, max=20.373, p(90)=18.968, p(95)=19.140, p(99)=20.127
- vus: min=1.000, max=1.000
- http_req_waiting: p(99)=19.891, avg=14.246, min=6.701, med=15.731, max=20.122, p(90)=18.740, p(95)=18.967
- http_req_failed: rate=0.000
- http_req_receiving: p(99)=0.593, avg=0.206, min=0.057, med=0.190, max=0.660, p(90)=0.297, p(95)=0.324
- http_req_duration{expected_response:true}: p(90)=18.968, p(95)=19.140, p(99)=20.127, avg=14.497, min=6.841, med=15.933, max=20.373
