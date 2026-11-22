# k6 summary

scenario: enrollments

- http_req_waiting: med=5.112, max=67.483, p(90)=6.682, p(95)=7.018, p(99)=31.099, avg=5.701, min=0.969
- http_req_connecting: p(99)=0.083, avg=0.002, min=0.000, med=0.000, max=0.107, p(90)=0.000, p(95)=0.000
- iterations: rate=24.091, count=243.000
- http_req_receiving: med=0.150, max=0.598, p(90)=0.296, p(95)=0.342, p(99)=0.443, avg=0.166, min=0.007
- vus: max=5.000, min=5.000
- http_req_duration: p(90)=6.967, p(95)=7.225, p(99)=31.262, avg=5.907, min=1.006, med=5.342, max=67.541
- http_req_sending: avg=0.040, min=0.008, med=0.039, max=0.190, p(90)=0.049, p(95)=0.058, p(99)=0.119
- http_req_duration{expected_response:true}: max=67.541, p(90)=6.967, p(95)=7.225, p(99)=31.262, avg=5.907, min=1.006, med=5.342
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_failed: rate=0.000
- http_req_blocked: max=0.147, p(90)=0.014, p(95)=0.017, p(99)=0.117, avg=0.014, min=0.002, med=0.011
