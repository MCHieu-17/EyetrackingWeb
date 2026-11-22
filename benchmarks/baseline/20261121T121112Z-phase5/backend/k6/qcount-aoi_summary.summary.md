# k6 summary

scenario: aoi_summary

- http_req_connecting: p(99)=0.079, avg=0.005, min=0.000, med=0.000, max=0.097, p(90)=0.000, p(95)=0.005
- vus: min=1.000, max=1.000
- http_req_failed: rate=0.000
- http_req_waiting: p(99)=227.207, avg=190.082, min=167.318, med=187.503, max=230.238, p(90)=213.921, p(95)=215.084
- http_req_sending: avg=0.067, min=0.015, med=0.062, max=0.203, p(90)=0.078, p(95)=0.087, p(99)=0.180
- http_req_duration: p(99)=228.050, avg=190.477, min=168.212, med=187.789, max=231.177, p(90)=214.221, p(95)=215.540
- http_req_duration{expected_response:true}: p(95)=215.540, p(99)=228.050, avg=190.477, min=168.212, med=187.789, max=231.177, p(90)=214.221
- http_req_blocked: avg=0.018, min=0.003, med=0.012, max=0.138, p(90)=0.014, p(95)=0.024, p(99)=0.115
- http_req_receiving: p(99)=0.889, avg=0.329, min=0.124, med=0.223, max=0.891, p(90)=0.748, p(95)=0.880
- http_req_tls_handshaking: min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000
- iterations: count=20.000, rate=2.555
