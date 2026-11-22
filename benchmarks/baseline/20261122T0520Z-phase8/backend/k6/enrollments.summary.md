# k6 summary

scenario: enrollments

- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_waiting: p(95)=7.114, p(99)=41.129, avg=6.212, min=0.872, med=5.871, max=75.581, p(90)=6.830
- http_req_connecting: p(99)=0.106, avg=0.002, min=0.000, med=0.000, max=0.109, p(90)=0.000, p(95)=0.000
- http_req_receiving: med=0.112, max=0.917, p(90)=0.269, p(95)=0.387, p(99)=0.657, avg=0.141, min=0.007
- http_req_blocked: p(99)=0.137, avg=0.013, min=0.002, med=0.011, max=0.140, p(90)=0.013, p(95)=0.019
- iterations: count=245.000, rate=24.052
- http_req_duration{expected_response:true}: max=75.650, p(90)=7.029, p(95)=7.315, p(99)=41.606, avg=6.389, min=0.941, med=6.004
- http_req_duration: med=6.004, max=75.650, p(90)=7.029, p(95)=7.315, p(99)=41.606, avg=6.389, min=0.941
- http_req_sending: min=0.007, med=0.038, max=0.076, p(90)=0.048, p(95)=0.054, p(99)=0.068, avg=0.037
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
