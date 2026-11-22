# k6 summary

scenario: enrollments

- http_req_duration: med=4.462, max=61.873, p(90)=7.149, p(95)=7.394, p(99)=31.967, avg=5.720, min=1.067
- http_req_receiving: p(99)=0.470, avg=0.171, min=0.009, med=0.166, max=0.639, p(90)=0.281, p(95)=0.328
- http_req_duration{expected_response:true}: avg=5.720, min=1.067, med=4.462, max=61.873, p(90)=7.149, p(95)=7.394, p(99)=31.967
- vus: max=5.000, min=5.000
- iterations: count=245.000, rate=24.041
- http_req_connecting: med=0.000, max=0.094, p(90)=0.000, p(95)=0.000, p(99)=0.093, avg=0.002, min=0.000
- http_req_blocked: p(99)=0.118, avg=0.013, min=0.002, med=0.011, max=0.124, p(90)=0.014, p(95)=0.016
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: p(90)=0.050, p(95)=0.056, p(99)=0.093, avg=0.039, min=0.007, med=0.038, max=0.145
- http_req_failed: rate=0.000
- http_req_waiting: avg=5.510, min=1.004, med=4.226, max=61.732, p(90)=6.862, p(95)=7.179, p(99)=31.836
