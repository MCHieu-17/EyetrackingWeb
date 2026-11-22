# k6 summary

scenario: enrollments

- http_req_connecting: min=0.000, med=0.000, max=0.091, p(90)=0.000, p(95)=0.005, p(99)=0.074, avg=0.005
- http_req_sending: max=0.056, p(90)=0.047, p(95)=0.055, p(99)=0.055, avg=0.039, min=0.013, med=0.040
- http_req_failed: rate=0.000
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- http_req_blocked: p(90)=0.013, p(95)=0.020, p(99)=0.104, avg=0.016, min=0.003, med=0.012, max=0.125
- iterations: rate=4.877, count=20.000
- http_req_duration: avg=3.935, min=1.069, med=4.151, max=6.698, p(90)=4.454, p(95)=4.743, p(99)=6.307
- http_req_duration{expected_response:true}: avg=3.935, min=1.069, med=4.151, max=6.698, p(90)=4.454, p(95)=4.743, p(99)=6.307
- http_req_receiving: med=0.127, max=0.194, p(90)=0.174, p(95)=0.191, p(99)=0.193, avg=0.127, min=0.036
- vus: max=1.000, min=1.000
- http_req_waiting: max=6.568, p(90)=4.292, p(95)=4.590, p(99)=6.172, avg=3.770, min=1.020, med=3.970
