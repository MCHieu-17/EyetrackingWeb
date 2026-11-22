# k6 summary

scenario: enrollments

- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_receiving: p(95)=0.357, p(99)=0.572, avg=0.155, min=0.008, med=0.126, max=1.516, p(90)=0.282
- http_req_blocked: p(99)=0.123, avg=0.013, min=0.002, med=0.011, max=0.150, p(90)=0.014, p(95)=0.018
- http_req_failed: rate=0.000
- http_req_connecting: min=0.000, med=0.000, max=0.099, p(90)=0.000, p(95)=0.000, p(99)=0.090, avg=0.002
- http_req_duration: p(90)=7.178, p(95)=7.425, p(99)=34.353, avg=5.535, min=1.057, med=4.522, max=56.088
- http_req_waiting: avg=5.343, min=1.009, med=4.328, max=56.012, p(90)=6.936, p(95)=7.180, p(99)=34.009
- http_req_sending: p(90)=0.048, p(95)=0.052, p(99)=0.065, avg=0.037, min=0.008, med=0.038, max=0.067
- iterations: rate=24.059, count=245.000
- vus: max=5.000, min=5.000
- http_req_duration{expected_response:true}: p(95)=7.425, p(99)=34.353, avg=5.535, min=1.057, med=4.522, max=56.088, p(90)=7.178
